from __future__ import annotations

import json
import sqlite3
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.db import get_db
from app.deps import current_user

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


@router.delete("/{lid}", status_code=204)
def delete_link(
    lid: int,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    _owned_link(conn, lid, user["id"])
    conn.execute("DELETE FROM links WHERE id = ?", (lid,))
