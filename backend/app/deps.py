from __future__ import annotations

import sqlite3

from fastapi import Cookie, Depends, HTTPException, Request

from app.db import get_db
from app.security import get_session_user


def current_user(
    request: Request,
    lipanel_session: str | None = Cookie(default=None),
    conn: sqlite3.Connection = Depends(get_db),
) -> sqlite3.Row:
    if not lipanel_session:
        raise HTTPException(status_code=401, detail="未登录")
    user = get_session_user(conn, lipanel_session)
    if user is None:
        raise HTTPException(status_code=401, detail="会话无效或已过期")
    conn.execute(
        "UPDATE sessions SET last_used_at = datetime('now') WHERE token = ?",
        (lipanel_session,),
    )
    return user
