from __future__ import annotations

import sqlite3

from fastapi import Depends, HTTPException, Request

from app.db import get_db
from app.security import get_session_user


def _session_token(request: Request) -> str | None:
    return request.cookies.get(request.app.state.settings.session_cookie)


def current_user(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> sqlite3.Row:
    token = _session_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    user = get_session_user(conn, token)
    if user is None:
        raise HTTPException(status_code=401, detail="会话无效或已过期")
    conn.execute(
        "UPDATE sessions SET last_used_at = datetime('now') WHERE token = ?",
        (token,),
    )
    return user


def optional_user(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> sqlite3.Row | None:
    token = _session_token(request)
    if not token:
        return None
    return get_session_user(conn, token)
