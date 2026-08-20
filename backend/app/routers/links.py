from __future__ import annotations

import json
import secrets
import sqlite3
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.db import get_db
from app.deps import current_user
from app.favicon import fetch_favicon, get_cached, set_cached

router = APIRouter(prefix="/api/links", tags=["links"])


def _validate_http_url(value: str | None) -> str | None:
    if value is None:
        return value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL 必须以 http:// 或 https:// 开头")
    return value


class LinkIn(BaseModel):
    group_id: int | None = None
    name: str = Field(min_length=1, max_length=100)
    url_lan: str
    url_wan: str | None = None
    icon_type: Literal["letter", "iconify", "upload"] = "letter"
    icon_value: str | None = None
    description: str = ""
    tags: list[str] = []
    is_public: bool = False
    guest_url_mode: Literal["hidden", "show"] = "hidden"
    sort_order: int = 0
    open_mode: Literal["new_tab", "modal"] = "new_tab"
    health_enabled: bool = True
    health_interval: int = Field(default=10, ge=1, le=1440)
    health_timeout: float = Field(default=5.0, ge=0.5, le=30.0)
    health_threshold: int = Field(default=1, ge=1, le=10)
    force: bool = False

    _url_lan = field_validator("url_lan")(_validate_http_url)
    _url_wan = field_validator("url_wan")(_validate_http_url)


class OrderIn(BaseModel):
    ordered_ids: list[int] = Field(min_length=1)


class BatchIdsIn(BaseModel):
    ids: list[int] = Field(min_length=1)


class BatchMoveIn(BatchIdsIn):
    group_id: int | None = None


class BatchVisibilityIn(BatchIdsIn):
    is_public: bool = False


def _owned_link(conn: sqlite3.Connection, lid: int, user_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM links WHERE id = ? AND user_id = ?", (lid, user_id)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="快捷方式不存在")
    return row


def _check_group(conn: sqlite3.Connection, group_id: int | None, user_id: int) -> None:
    if group_id is None:
        return
    row = conn.execute(
        "SELECT id FROM groups WHERE id = ? AND user_id = ?", (group_id, user_id)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="分组不存在")


def _link_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["tags"] = json.loads(data["tags"] or "[]")
    return data


def _owned_link_ids(
    conn: sqlite3.Connection, ids: list[int], user_id: int
) -> list[int]:
    """校验全部 id 归属本人，返回存在的 id；任一非本人/不存在 → 404。"""
    owned = {
        r["id"]
        for r in conn.execute(
            "SELECT id FROM links WHERE user_id = ?", (user_id,)
        ).fetchall()
    }
    for lid in ids:
        if lid not in owned:
            raise HTTPException(status_code=404, detail="快捷方式不存在")
    return ids


@router.post("/batch-delete", status_code=200)
def batch_delete_links(
    body: BatchIdsIn,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    ids = _owned_link_ids(conn, body.ids, user["id"])
    placeholders = ",".join("?" for _ in ids)
    conn.execute(
        f"DELETE FROM links WHERE id IN ({placeholders}) AND user_id = ?",
        (*ids, user["id"]),
    )
    return {"deleted": len(ids)}


@router.post("/batch-move", status_code=200)
def batch_move_links(
    body: BatchMoveIn,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    ids = _owned_link_ids(conn, body.ids, user["id"])
    _check_group(conn, body.group_id, user["id"])
    placeholders = ",".join("?" for _ in ids)
    conn.execute(
        f"UPDATE links SET group_id = ? WHERE id IN ({placeholders}) AND user_id = ?",
        (body.group_id, *ids, user["id"]),
    )
    return {"moved": len(ids)}


@router.post("/batch-visibility", status_code=200)
def batch_visibility_links(
    body: BatchVisibilityIn,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    ids = _owned_link_ids(conn, body.ids, user["id"])
    placeholders = ",".join("?" for _ in ids)
    conn.execute(
        f"UPDATE links SET is_public = ? WHERE id IN ({placeholders}) AND user_id = ?",
        (int(body.is_public), *ids, user["id"]),
    )
    return {"updated": len(ids)}


@router.patch("/order")
def order_links(
    body: OrderIn,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """整组写入链接顺序：ordered_ids 必须是本人链接（可含子集），按列表下标重排。"""
    if len(set(body.ordered_ids)) != len(body.ordered_ids):
        raise HTTPException(status_code=400, detail="排序列表包含重复项")
    owned = conn.execute(
        "SELECT id FROM links WHERE user_id = ? ORDER BY sort_order, id",
        (user["id"],),
    ).fetchall()
    owned_ids = {r["id"] for r in owned}
    for lid in body.ordered_ids:
        if lid not in owned_ids:
            raise HTTPException(status_code=404, detail="快捷方式不存在")
    # 整体重排：提供的 id 按列表顺序前置，其余链接保持原相对顺序在后，
    # 避免与默认 sort_order=0 的未参与项产生并列歧义。
    provided = set(body.ordered_ids)
    new_order = list(body.ordered_ids) + [
        r["id"] for r in owned if r["id"] not in provided
    ]
    for index, lid in enumerate(new_order):
        conn.execute(
            "UPDATE links SET sort_order = ? WHERE id = ? AND user_id = ?",
            (index, lid, user["id"]),
        )
    return {"ok": True}


@router.get("")
def list_links(
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM links WHERE user_id = ? ORDER BY sort_order, id", (user["id"],)
    ).fetchall()
    return [_link_dict(r) for r in rows]


def _check_duplicate(
    conn: sqlite3.Connection,
    user_id: int,
    name: str,
    url_lan: str,
    exclude_id: int | None = None,
) -> None:
    for row in conn.execute(
        "SELECT id, name, url_lan FROM links WHERE user_id = ?", (user_id,)
    ).fetchall():
        if row["id"] == exclude_id:
            continue
        if row["name"].strip().lower() == name.strip().lower():
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "duplicate",
                    "message": f"已存在同名快捷方式「{row['name']}」",
                },
            )
        if row["url_lan"] == url_lan:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "duplicate",
                    "message": f"已存在相同地址的快捷方式「{row['name']}」",
                },
            )


def _auto_fetch_icon(request: Request, link_id: int, url: str) -> None:
    """后台自动获取站点 favicon：失败静默，不影响创建/编辑响应。"""
    settings = request.app.state.settings
    try:
        from app.db import connect

        data = fetch_favicon(url)
        if data is None:
            set_cached(link_id, None)
            return
        name = f"link-{link_id}-{secrets.token_hex(4)}.png"
        favicons_dir = settings.data_dir / "favicons"
        favicons_dir.mkdir(parents=True, exist_ok=True)
        (favicons_dir / name).write_bytes(data)
        path = f"/favicons/{name}"
        set_cached(link_id, path)
        conn = connect(settings.db_path)
        conn.execute(
            "UPDATE links SET icon_type = 'upload', icon_value = ? "
            "WHERE id = ? AND icon_type = 'letter'",
            (path, link_id),
        )
        conn.close()
    except Exception:
        pass


def _maybe_schedule_icon_fetch(
    request: Request,
    background_tasks: BackgroundTasks,
    link_id: int,
    body: LinkIn,
) -> None:
    """新建/编辑未使用自定义图标且开关开启时，自动后台抓取 favicon。"""
    settings = request.app.state.settings
    if not settings.link_icon_fetch or body.icon_type != "letter":
        return
    url = body.url_wan or body.url_lan
    background_tasks.add_task(_auto_fetch_icon, request, link_id, url)


@router.post("", status_code=201)
def create_link(
    body: LinkIn,
    request: Request,
    background_tasks: BackgroundTasks,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    _check_group(conn, body.group_id, user["id"])
    if not body.force:
        _check_duplicate(conn, user["id"], body.name, body.url_lan)
    cur = conn.execute(
        "INSERT INTO links (user_id, group_id, name, url_lan, url_wan, icon_type, "
        "icon_value, description, tags, is_public, guest_url_mode, sort_order, open_mode, "
        "health_enabled, health_interval, health_timeout, health_threshold) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user["id"],
            body.group_id,
            body.name,
            body.url_lan,
            body.url_wan,
            body.icon_type,
            body.icon_value,
            body.description,
            json.dumps(body.tags, ensure_ascii=False),
            int(body.is_public),
            body.guest_url_mode,
            body.sort_order,
            body.open_mode,
            int(body.health_enabled),
            body.health_interval,
            body.health_timeout,
            body.health_threshold,
        ),
    )
    link_id = int(cur.lastrowid)
    _maybe_schedule_icon_fetch(request, background_tasks, link_id, body)
    return _link_dict(_owned_link(conn, link_id, user["id"]))


@router.put("/{lid}")
def update_link(
    lid: int,
    body: LinkIn,
    request: Request,
    background_tasks: BackgroundTasks,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    _owned_link(conn, lid, user["id"])
    _check_group(conn, body.group_id, user["id"])
    if not body.force:
        _check_duplicate(conn, user["id"], body.name, body.url_lan, exclude_id=lid)
    conn.execute(
        "UPDATE links SET group_id = ?, name = ?, url_lan = ?, url_wan = ?, "
        "icon_type = ?, icon_value = ?, description = ?, tags = ?, is_public = ?, "
        "guest_url_mode = ?, sort_order = ?, open_mode = ?, health_enabled = ?, "
        "health_interval = ?, health_timeout = ?, health_threshold = ? WHERE id = ?",
        (
            body.group_id,
            body.name,
            body.url_lan,
            body.url_wan,
            body.icon_type,
            body.icon_value,
            body.description,
            json.dumps(body.tags, ensure_ascii=False),
            int(body.is_public),
            body.guest_url_mode,
            body.sort_order,
            body.open_mode,
            int(body.health_enabled),
            body.health_interval,
            body.health_timeout,
            body.health_threshold,
            lid,
        ),
    )
    _maybe_schedule_icon_fetch(request, background_tasks, lid, body)
    return _link_dict(_owned_link(conn, lid, user["id"]))


@router.post("/{lid}/fetch-icon")
def fetch_link_icon(
    lid: int,
    request: Request,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """抓取站点 favicon 并写回链接图标（受控出站：开关/超时/并发/缓存/白名单）。"""
    settings = request.app.state.settings
    if not settings.link_icon_fetch:
        raise HTTPException(status_code=400, detail="图标抓取已关闭")
    _owned_link(conn, lid, user["id"])
    cached = get_cached(lid)
    if cached is not None:
        conn.execute(
            "UPDATE links SET icon_type = 'upload', icon_value = ? WHERE id = ?",
            (cached, lid),
        )
        return _link_dict(_owned_link(conn, lid, user["id"]))
    row = _owned_link(conn, lid, user["id"])
    url = row["url_wan"] or row["url_lan"]
    data = fetch_favicon(url)
    if data is None:
        set_cached(lid, None)
        raise HTTPException(status_code=404, detail="未找到站点图标")
    name = f"link-{lid}-{secrets.token_hex(4)}.png"
    favicons_dir = settings.data_dir / "favicons"
    favicons_dir.mkdir(parents=True, exist_ok=True)
    (favicons_dir / name).write_bytes(data)
    path = f"/favicons/{name}"
    set_cached(lid, path)
    conn.execute(
        "UPDATE links SET icon_type = 'upload', icon_value = ? WHERE id = ?",
        (path, lid),
    )
    return _link_dict(_owned_link(conn, lid, user["id"]))


@router.delete("/{lid}", status_code=204)
def delete_link(
    lid: int,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    _owned_link(conn, lid, user["id"])
    conn.execute("DELETE FROM links WHERE id = ?", (lid,))
