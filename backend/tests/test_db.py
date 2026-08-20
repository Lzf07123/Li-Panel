from pathlib import Path

from app.db import connect, count_users, create_user, init_schema


def test_schema_and_user(tmp_path: Path):
    conn = connect(tmp_path / "test.db")
    init_schema(conn)
    assert count_users(conn) == 0
    uid = create_user(conn, "admin", "hash", "salt", "admin")
    assert count_users(conn) == 1
    assert uid > 0
    conn.close()
