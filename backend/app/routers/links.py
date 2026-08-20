from __future__ import annotations

import json
import secrets
import sqlite3
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
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

    _url_lan = field_validator("url_lan")(_validate_http_url)
    _url_wan = field_validator("url_wan")(_validate_http_url)


class OrderIn(BaseModel):
    ordered_ids: list[int] = Field(min_length=1)


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


@router.post("", status_code=201)
def create_link(
    body: LinkIn,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    _check_group(conn, body.group_id, user["id"])
    cur = conn.execute(
        "INSERT INTO links (user_id, group_id, name, url_lan, url_wan, icon_type, "
        "icon_value, description, tags, is_public, guest_url_mode, sort_order, open_mode) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
        ),
    )
    return _link_dict(_owned_link(conn, cur.lastrowid, user["id"]))


@router.put("/{lid}")
def update_link(
    lid: int,
    body: LinkIn,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    _owned_link(conn, lid, user["id"])
    _check_group(conn, body.group_id, user["id"])
    conn.execute(
        "UPDATE links SET group_id = ?, name = ?, url_lan = ?, url_wan = ?, "
        "icon_type = ?, icon_value = ?, description = ?, tags = ?, is_public = ?, "
        "guest_url_mode = ?, sort_order = ?, open_mode = ? WHERE id = ?",
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
            lid,
        ),
    )
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
