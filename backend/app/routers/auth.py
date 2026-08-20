from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.db import get_db, get_user_by_username
from app.deps import current_user
from app.security import create_session, delete_session, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


def _user_payload(user: sqlite3.Row) -> dict:
    return {"id": user["id"], "username": user["username"], "role": user["role"]}


@router.post("/login")
def login(
    body: LoginIn,
    response: Response,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    ip = request.client.host if request.client else "unknown"
    if not request.app.state.login_limiter.allow(ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    user = get_user_by_username(conn, body.username)
    if user is None or not verify_password(body.password, user["password_hash"], user["salt"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    settings = request.app.state.settings
    token = create_session(conn, user["id"], session_days=settings.session_days)
    response.set_cookie(
        "lipanel_session",
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return {"user": _user_payload(user)}


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    lipanel_session: Annotated[str | None, Cookie()] = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    if lipanel_session:
        delete_session(conn, lipanel_session)
    response.delete_cookie("lipanel_session", path="/")


@router.get("/me")
def me(
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    identity = conn.execute(
        "SELECT provider, email FROM sso_identities WHERE user_id = ? ORDER BY id LIMIT 1",
        (user["id"],),
    ).fetchone()
    return {
        "user": _user_payload(user),
        "sso": {
            "bound": identity is not None,
            "provider": identity["provider"] if identity else None,
            "email": identity["email"] if identity else None,
        },
    }
