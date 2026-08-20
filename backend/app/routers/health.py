from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.db import get_db
from app.deps import current_user
from app.health import check_url, get_cached, set_cached

router = APIRouter(prefix="/api/health", tags=["health"])

MAX_WORKERS = 4
SAMPLE_INTERVAL_MINUTES = 10
HISTORY_HOURS = 24
MAX_HISTORY_ROWS = 144


def _effective_url(link: sqlite3.Row) -> str:
    return link["url_wan"] or link["url_lan"]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/links")
def health_links(
    request: Request,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """当前用户全部链接的健康状态（up/down/unknown + 响应毫秒），并发 ≤4。"""
    settings = request.app.state.settings
    if not settings.health_check:
        return {"enabled": False, "results": []}
    links = conn.execute(
        "SELECT id, url_lan, url_wan FROM links WHERE user_id = ?", (user["id"],)
    ).fetchall()

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
            pool.submit(check_url, _effective_url(link)): link_id
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

    _record_samples(conn, user["id"], results)
    return {"enabled": True, "results": results}


def _record_samples(
    conn: sqlite3.Connection, user_id: int, results: list[dict]
) -> None:
    """V23：每链接 ≥10 分钟采样一次写入 link_health，超 144 条滚动清理。"""
    now = _now_utc()
    fmt = now.strftime("%Y-%m-%d %H:%M:%S")
    for item in results:
        link_id = item["link_id"]
        last = conn.execute(
            "SELECT checked_at FROM link_health WHERE link_id = ? "
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
                minutes=SAMPLE_INTERVAL_MINUTES
            ):
                continue
        conn.execute(
            "DELETE FROM link_health WHERE link_id = ? AND id NOT IN ("
            "SELECT id FROM link_health WHERE link_id = ? "
            "ORDER BY checked_at DESC LIMIT ?)",
            (link_id, link_id, MAX_HISTORY_ROWS - 1),
        )
        conn.execute(
            "INSERT INTO link_health (link_id, user_id, status, ms, checked_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (link_id, user_id, item["status"], item["ms"], fmt),
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
