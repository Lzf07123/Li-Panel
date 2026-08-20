from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterator

from fastapi import Request


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sso_identities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    subject TEXT NOT NULL,
    email TEXT,
    nickname TEXT,
    avatar TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at TEXT,
    UNIQUE(provider, subject)
);
CREATE INDEX IF NOT EXISTS idx_sso_identities_user ON sso_identities(user_id);

CREATE TABLE IF NOT EXISTS sso_flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL,
    nonce TEXT NOT NULL,
    code_verifier TEXT NOT NULL,
    subject TEXT,
    sid TEXT,
    email TEXT,
    nickname TEXT,
    avatar TEXT,
    redirect_after TEXT NOT NULL DEFAULT '/',
    expires_at TEXT NOT NULL,
    consumed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sso_sid TEXT,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_used_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    icon TEXT,
    is_public INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_groups_user ON groups(user_id);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    url_lan TEXT NOT NULL,
    url_wan TEXT,
    icon_type TEXT NOT NULL DEFAULT 'letter',
    icon_value TEXT,
    description TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    is_public INTEGER NOT NULL DEFAULT 0,
    guest_url_mode TEXT NOT NULL DEFAULT 'hidden',
    sort_order INTEGER NOT NULL DEFAULT 0,
    open_mode TEXT NOT NULL DEFAULT 'new_tab',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_links_user ON links(user_id);
CREATE INDEX IF NOT EXISTS idx_links_group ON links(group_id);

CREATE TABLE IF NOT EXISTS settings (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    UNIQUE(user_id, key)
);

CREATE TABLE IF NOT EXISTS site_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS link_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id INTEGER NOT NULL REFERENCES links(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    ms INTEGER NOT NULL DEFAULT 0,
    fail_count INTEGER NOT NULL DEFAULT 0,
    checked_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_link_health_link ON link_health(link_id, checked_at);
"""



def connect(path: Path) -> sqlite3.Connection:
    # FastAPI 同步依赖可能在不同线程池线程中执行，同一请求的连接串行使用，
    # 因此关闭 SQLite 的跨线程检查（每个请求拥有独立连接，无并发共享）。
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


_DATA_MUTATION_PREFIXES = (
    "/api/groups", "/api/links", "/api/tags", "/api/settings",
    "/api/site-settings", "/api/backup",
)


def _maybe_write_snapshot(request: Request, conn: sqlite3.Connection) -> None:
    """数据变更提交后写自动快照（V19）；仅当连接实际有变更且路径属于数据接口。"""
    if conn.total_changes == 0:
        return
    if not request.url.path.startswith(_DATA_MUTATION_PREFIXES):
        return
    from app.snapshot import write_snapshot

    settings = request.app.state.settings
    write_snapshot(settings.data_dir, settings.db_path, settings.backup_keep)


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    """FastAPI 依赖：请求级 SQLite 连接，结束自动 commit/close。"""
    db_path: Path = request.app.state.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    before = conn.total_changes
    try:
        yield conn
        conn.commit()
        if conn.total_changes > before:
            _maybe_write_snapshot(request, conn)
    finally:
        conn.close()


def count_users(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def create_user(
    conn: sqlite3.Connection,
    username: str,
    password_hash: str,
    salt: str,
    role: str = "user",
) -> int:
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, salt, role) VALUES (?, ?, ?, ?)",
        (username, password_hash, salt, role),
    )
    return int(cur.lastrowid)


def get_user_by_username(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
    ).fetchone()
