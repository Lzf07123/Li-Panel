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


class OrderIn(BaseModel):
    ordered_ids: list[int] = Field(min_length=1)


def _owned_group(conn: sqlite3.Connection, gid: int, user_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM groups WHERE id = ? AND user_id = ?", (gid, user_id)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="分组不存在")
    return row


@router.patch("/order")
def order_groups(
    body: OrderIn,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """整组写入分组顺序：提供的 id 前置整体重排，其余保持原相对顺序。"""
    if len(set(body.ordered_ids)) != len(body.ordered_ids):
        raise HTTPException(status_code=400, detail="排序列表包含重复项")
    owned = conn.execute(
        "SELECT id FROM groups WHERE user_id = ? ORDER BY sort_order, id",
        (user["id"],),
    ).fetchall()
    owned_ids = {r["id"] for r in owned}
    for gid in body.ordered_ids:
        if gid not in owned_ids:
            raise HTTPException(status_code=404, detail="分组不存在")
    provided = set(body.ordered_ids)
    new_order = list(body.ordered_ids) + [
        r["id"] for r in owned if r["id"] not in provided
    ]
    for index, gid in enumerate(new_order):
        conn.execute(
            "UPDATE groups SET sort_order = ? WHERE id = ? AND user_id = ?",
            (index, gid, user["id"]),
        )
    return {"ok": True}


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
