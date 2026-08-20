from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.deps import current_user

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])


@router.get("")
def list_audit_logs(
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
    limit: int = 200,
) -> list[dict]:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可查看审计日志")
    limit = max(1, min(limit, 1000))
    rows = conn.execute(
        "SELECT id, user_id, action, detail, created_at FROM audit_logs "
        "ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
