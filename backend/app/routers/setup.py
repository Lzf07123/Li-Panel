from __future__ import annotations

import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.db import count_users, create_user, get_db
from app.security import hash_password

router = APIRouter(prefix="/api", tags=["setup"])

USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")

class SetupIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)


def validate_username(username: str) -> None:
    if not USERNAME_RE.match(username):
        raise HTTPException(status_code=422, detail="用户名需为 3-32 位字母/数字/_/-")


@router.get("/setup-status")
def setup_status(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return {"required": count_users(conn) == 0}


@router.post("/setup", status_code=201)
def setup(
    body: SetupIn,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    ip = request.client.host if request.client else "unknown"
    if not request.app.state.setup_limiter.allow(ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    if count_users(conn) > 0:
        raise HTTPException(status_code=409, detail="已初始化，不能重复创建管理员")
    validate_username(body.username)
    password_hash, salt = hash_password(body.password)
    uid = create_user(conn, body.username, password_hash, salt, role="admin")
    return {"id": uid}
