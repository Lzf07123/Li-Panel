from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from app.db import get_db
from app.deps import current_user

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _current_session_id(conn, token: str | None, user_id: int) -> int | None:
    if not token:
        return None
    row = conn.execute(
        "SELECT id FROM sessions WHERE token = ? AND user_id = ?", (token, user_id)
    ).fetchone()
    return row["id"] if row is not None else None


@router.get("")
def list_sessions(
    request: Request,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    token = request.cookies.get(request.app.state.settings.session_cookie)
    current_id = _current_session_id(conn, token, user["id"])
    rows = conn.execute(
        "SELECT id, created_at, last_used_at, expires_at FROM sessions "
        "WHERE user_id = ? ORDER BY last_used_at DESC",
        (user["id"],),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "created_at": row["created_at"],
            "last_used_at": row["last_used_at"],
            "expires_at": row["expires_at"],
            "current": row["id"] == current_id,
        }
        for row in rows
    ]


def _owned_session(conn, sid: int, user_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM sessions WHERE id = ? AND user_id = ?", (sid, user_id)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return row


@router.delete("/{sid}", status_code=200)
def revoke_session(
    sid: int,
    request: Request,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = _owned_session(conn, sid, user["id"])
    token = request.cookies.get(request.app.state.settings.session_cookie)
    if token and row["token"] == token:
        raise HTTPException(status_code=400, detail="不能吊销当前会话")
    conn.execute("DELETE FROM sessions WHERE id = ?", (sid,))
    return {"revoked": 1}


@router.delete("", status_code=200)
def revoke_all_sessions(
    request: Request,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    token = request.cookies.get(request.app.state.settings.session_cookie)
    if token:
        before = conn.execute(
            "SELECT COUNT(*) AS n FROM sessions WHERE user_id = ? AND token != ?",
            (user["id"], token),
        ).fetchone()["n"]
        conn.execute(
            "DELETE FROM sessions WHERE user_id = ? AND token != ?",
            (user["id"], token),
        )
        return {"revoked": before}
    before = conn.execute(
        "SELECT COUNT(*) AS n FROM sessions WHERE user_id = ?", (user["id"],)
    ).fetchone()["n"]
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
    return {"revoked": before}
