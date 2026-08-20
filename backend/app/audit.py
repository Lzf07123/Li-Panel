"""审计日志：关键安全/数据事件写入 audit_logs，滚动保留最近 1000 条。"""
from __future__ import annotations

import sqlite3

AUDIT_MAX_ROWS = 1000


def write_audit(
    conn: sqlite3.Connection, user_id: int, action: str, detail: str = ""
) -> None:
    try:
        conn.execute(
            "INSERT INTO audit_logs (user_id, action, detail) VALUES (?, ?, ?)",
            (user_id, action, detail[:500]),
        )
        conn.execute(
            "DELETE FROM audit_logs WHERE id NOT IN ("
            "SELECT id FROM audit_logs ORDER BY id DESC LIMIT ?)",
            (AUDIT_MAX_ROWS,),
        )
    except sqlite3.Error:
        pass
