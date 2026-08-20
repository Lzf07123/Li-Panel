def _user_b_headers(client):
    from app.db import connect
    from app.security import hash_password

    conn = connect(client.app.state.db_path)
    ph, salt = hash_password("secret123")
    conn.execute(
        "INSERT INTO users (username, password_hash, salt, role) VALUES ('user_b', ?, ?, 'user')",
        (ph, salt),
    )
    conn.commit()
    conn.close()
    b = client.post(
        "/api/auth/login", json={"username": "user_b", "password": "secret123"}
    )
    return {"Cookie": f"lipanel_session={b.cookies['lipanel_session']}"}


def test_user_cannot_update_site_settings(client, auth_headers):
    bh = _user_b_headers(client)
    assert (
        client.put("/api/site-settings", json={"site_name": "X"}, headers=bh).status_code
        == 403
    )
    # admin 可以
    assert (
        client.put(
            "/api/site-settings", json={"site_name": "X"}, headers=auth_headers
        ).status_code
        == 200
    )


def test_user_can_read_site_settings(client, bh=None):
    bh = _user_b_headers(client)
    assert client.get("/api/site-settings", headers=bh).status_code == 200


def test_admin_me_includes_role(client, auth_headers):
    me = client.get("/api/auth/me", headers=auth_headers).json()
    assert me["user"]["role"] == "admin"
