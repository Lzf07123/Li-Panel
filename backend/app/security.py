from __future__ import annotations

import base64
import hashlib
import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SALT_BYTES = 16


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode())


def hash_password(password: str) -> tuple[str, str]:
    salt = os.urandom(SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return _b64(digest), _b64(salt)


def verify_password(password: str, hash_b64: str, salt_b64: str) -> bool:
    try:
        digest = hashlib.scrypt(
            password.encode(),
            salt=_unb64(salt_b64),
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            dklen=SCRYPT_DKLEN,
        )
    except ValueError:
        return False
    return secrets.compare_digest(digest, _unb64(hash_b64))


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def create_session(
    conn: sqlite3.Connection,
    user_id: int,
    sso_sid: str | None = None,
    sso_id_token: str | None = None,
    session_days: int = 30,
) -> str:
    token = new_token()
    now = _now_utc()
    expires = now + timedelta(days=session_days)
    conn.execute(
        "INSERT INTO sessions (token, user_id, sso_sid, sso_id_token, expires_at, created_at, last_used_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (token, user_id, sso_sid, sso_id_token, _fmt(expires), _fmt(now), _fmt(now)),
    )
    return token


def get_session_user(
    conn: sqlite3.Connection, token: str
) -> sqlite3.Row | None:
    row = conn.execute(
        "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token = ? AND s.expires_at > ?",
        (token, _fmt(_now_utc())),
    ).fetchone()
    return row


def delete_session(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


class RateLimiter:
    """固定窗口内存限流：window_seconds 内最多 limit 次。"""

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = [t for t in self._hits.get(key, []) if now - t < self.window]
        if len(hits) >= self.limit:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True
