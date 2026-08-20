from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.brand_defaults import get_site_settings
from app.db import get_db
from app.deps import current_user
from app.health import check_url, get_cached, set_cached
from app.notify import send_notification

router = APIRouter(prefix="/api/health", tags=["health"])

MAX_WORKERS = 4
SAMPLE_INTERVAL_MINUTES = 10
HISTORY_HOURS = 24
MAX_HISTORY_ROWS = 144

LINK_COLS = (
    "id, name, url_lan, url_wan, health_enabled, health_interval, "
    "health_timeout, health_threshold"
)


def _effective_url(link: sqlite3.Row) -> str:
    return link["url_wan"] or link["url_lan"]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _check_many(links: list[sqlite3.Row]) -> list[dict]:
    """并发 ≤4 检查链接列表（按链接自身超时），返回按 link_id 排序的结果。"""
    results: list[dict] = []
    pending: dict = {}
    for link in links:
        cached = get_cached(link["id"])
        if cached is not None:
            status, ms = cached
            results.append(
                {
                    "link_id": link["id"],
                    "status": status,
                    "ms": ms,
                    "checked_at": _now_utc().isoformat(),
                }
            )
        else:
            pending[link["id"]] = link
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(
                check_url, _effective_url(link), link["health_timeout"]
            ): link_id
            for link_id, link in pending.items()
        }
        for future in as_completed(futures):
            link_id = futures[future]
            status, ms = future.result()
            set_cached(link_id, status, ms)
            results.append(
                {
                    "link_id": link_id,
                    "status": status,
                    "ms": ms,
                    "checked_at": _now_utc().isoformat(),
                }
            )
    results.sort(key=lambda item: item["link_id"])
    return results


@router.get("/links")
def health_links(
    request: Request,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """当前用户全部启用检测链接的健康状态；每链接开关/间隔/超时/阈值。"""
    settings = request.app.state.settings
    if not settings.health_check:
        return {"enabled": False, "results": []}
    links = conn.execute(
        f"SELECT {LINK_COLS} FROM links WHERE user_id = ? AND health_enabled = 1",
        (user["id"],),
    ).fetchall()
    results = _check_many(links)
    _record_samples(conn, user["id"], results, links)
    return {"enabled": True, "results": results}


@router.get("/status")
def public_status(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """公开状态页：仅公开且启用检测的链接可用性汇总（访客可读）。"""
    settings = request.app.state.settings
    site = get_site_settings(conn)
    if not (site.get("public_mode", "true") == "true" and settings.public_mode):
        raise HTTPException(status_code=401, detail="访客视图已关闭")
    if not settings.health_check:
        return {"enabled": False, "results": []}
    links = conn.execute(
        f"SELECT {LINK_COLS} FROM links WHERE is_public = 1 AND health_enabled = 1"
    ).fetchall()
    return {"enabled": True, "results": _check_many(links)}


def _record_samples(
    conn: sqlite3.Connection,
    user_id: int,
    results: list[dict],
    links: list[sqlite3.Row] | None = None,
) -> None:
    """采样写 link_health（每链接按自身间隔），应用失败阈值，状态变化发通知。"""
    cfg = {row["id"]: row for row in links or []}
    notify_row = conn.execute(
        "SELECT key, value FROM site_settings WHERE key IN ('notify_url', 'notify_enabled')"
    ).fetchall()
    notify_config = {row["key"]: row["value"] for row in notify_row}
    notify_url = notify_config.get("notify_url", "")
    notify_enabled = notify_config.get("notify_enabled", "false") == "true"

    now = _now_utc()
    fmt = now.strftime("%Y-%m-%d %H:%M:%S")
    for item in results:
        link_id = item["link_id"]
        link_cfg = cfg.get(link_id)
        interval = (
            link_cfg["health_interval"]
            if link_cfg is not None
            else SAMPLE_INTERVAL_MINUTES
        )
        threshold = (
            link_cfg["health_threshold"] if link_cfg is not None else 1
        )
        last = conn.execute(
            "SELECT checked_at, status, fail_count FROM link_health WHERE link_id = ? "
            "ORDER BY checked_at DESC LIMIT 1",
            (link_id,),
        ).fetchone()
        if last is not None:
            try:
                last_dt = datetime.strptime(
                    last["checked_at"], "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                last_dt = None
            if last_dt is not None and (now - last_dt) < timedelta(
                minutes=interval
            ):
                continue
        prev_status = last["status"] if last is not None else None
        prev_fail = last["fail_count"] if last is not None else 0
        fail_count = prev_fail + 1 if item["status"] == "down" else 0
        effective = item["status"]
        if item["status"] == "down" and fail_count < threshold:
            effective = "up"  # 连续失败未达阈值，暂按可用处理
        item["status"] = effective
        conn.execute(
            "DELETE FROM link_health WHERE link_id = ? AND id NOT IN ("
            "SELECT id FROM link_health WHERE link_id = ? "
            "ORDER BY checked_at DESC LIMIT ?)",
            (link_id, link_id, MAX_HISTORY_ROWS - 1),
        )
        conn.execute(
            "INSERT INTO link_health (link_id, user_id, status, ms, fail_count, checked_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (link_id, user_id, effective, item["ms"], fail_count, fmt),
        )
        if notify_enabled and notify_url and prev_status != effective:
            send_notification(
                notify_url,
                {
                    "event": "link_status_changed",
                    "link_id": link_id,
                    "name": cfg[link_id]["name"] if link_id in cfg else "",
                    "status": effective,
                    "previous_status": prev_status,
                    "ms": item["ms"],
                    "checked_at": fmt,
                },
            )
    cutoff = (now - timedelta(hours=HISTORY_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "DELETE FROM link_health WHERE user_id = ? AND checked_at < ?",
        (user_id, cutoff),
    )


@router.get("/links/{lid}/history")
def link_history(
    lid: int,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """最近 24h 状态历史（每链接最多 144 条，供趋势条渲染）。"""
    row = conn.execute(
        "SELECT id FROM links WHERE id = ? AND user_id = ?", (lid, user["id"])
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="快捷方式不存在")
    rows = conn.execute(
        "SELECT status, ms, checked_at FROM link_health "
        "WHERE link_id = ? AND user_id = ? ORDER BY checked_at DESC LIMIT ?",
        (lid, user["id"], MAX_HISTORY_ROWS),
    ).fetchall()
    return [dict(r) for r in rows]
