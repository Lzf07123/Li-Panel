from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import get_db
from app.deps import current_user

router = APIRouter(prefix="/api/groups", tags=["groups"])


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    icon: str | None = None
    is_public: bool = False
    sort_order: int = 0


def _owned_group(conn: sqlite3.Connection, gid: int, user_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM groups WHERE id = ? AND user_id = ?", (gid, user_id)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="分组不存在")
    return row


@router.get("")
def list_groups(
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM groups WHERE user_id = ? ORDER BY sort_order, id", (user["id"],)
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("", status_code=201)
def create_group(
    body: GroupIn,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    cur = conn.execute(
        "INSERT INTO groups (user_id, name, icon, is_public, sort_order) VALUES (?, ?, ?, ?, ?)",
        (user["id"], body.name, body.icon, int(body.is_public), body.sort_order),
    )
    return dict(_owned_group(conn, cur.lastrowid, user["id"]))


@router.put("/{gid}")
def update_group(
    gid: int,
    body: GroupIn,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    _owned_group(conn, gid, user["id"])
    conn.execute(
        "UPDATE groups SET name = ?, icon = ?, is_public = ?, sort_order = ? WHERE id = ?",
        (body.name, body.icon, int(body.is_public), body.sort_order, gid),
    )
    return dict(_owned_group(conn, gid, user["id"]))


@router.delete("/{gid}", status_code=204)
def delete_group(
    gid: int,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    _owned_group(conn, gid, user["id"])
    conn.execute(
        "UPDATE links SET group_id = NULL WHERE group_id = ? AND user_id = ?",
        (gid, user["id"]),
    )
    conn.execute("DELETE FROM groups WHERE id = ?", (gid,))
