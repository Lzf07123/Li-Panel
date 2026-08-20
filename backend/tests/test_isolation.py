from app.db import connect
from app.security import hash_password


def test_cross_user_isolation(client, admin):
    # 直接向测试库插入第二个用户，模拟 SSO 新建账号
    conn = connect(client.app.state.db_path)
    password_hash, salt = hash_password("secret123")
    conn.execute(
        "INSERT INTO users (username, password_hash, salt, role) VALUES ('user_b', ?, ?, 'user')",
        (password_hash, salt),
    )
    conn.commit()
    conn.close()

    a = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )
    b = client.post(
        "/api/auth/login", json={"username": "user_b", "password": "secret123"}
    )
    ah = {"Cookie": f"lipanel_session={a.cookies['lipanel_session']}"}
    bh = {"Cookie": f"lipanel_session={b.cookies['lipanel_session']}"}
    gid = client.post("/api/groups", json={"name": "A组"}, headers=ah).json()["id"]
    assert (
        client.put(f"/api/groups/{gid}", json={"name": "X"}, headers=bh).status_code
        == 404
    )
    assert client.delete(f"/api/groups/{gid}", headers=bh).status_code == 404
