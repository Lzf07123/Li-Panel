from pathlib import Path

from app.db import connect, create_user, init_schema
from app.security import (
    RateLimiter,
    create_session,
    delete_session,
    get_session_user,
    hash_password,
    verify_password,
)


def test_scrypt_roundtrip():
    h, s = hash_password("secret123")
    assert verify_password("secret123", h, s)
    assert not verify_password("wrong", h, s)


def test_session_lifecycle(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    init_schema(conn)
    uid = create_user(conn, "admin", "h", "s", "admin")
    token = create_session(conn, uid)
    row = get_session_user(conn, token)
    assert row["id"] == uid
    delete_session(conn, token)
    assert get_session_user(conn, token) is None
    conn.close()


def test_rate_limiter():
    rl = RateLimiter(limit=2, window_seconds=60)
    assert rl.allow("a") and rl.allow("a")
    assert not rl.allow("a")
    assert rl.allow("b")
