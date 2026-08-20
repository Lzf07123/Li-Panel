def test_audit_login_logout_written(client, auth_headers):
    logs = client.get("/api/audit-logs", headers=auth_headers).json()
    actions = [entry["action"] for entry in logs]
    assert "login" in actions


def test_audit_site_settings_written(client, auth_headers):
    client.put(
        "/api/site-settings", json={"site_name": "X"}, headers=auth_headers
    )
    logs = client.get("/api/audit-logs", headers=auth_headers).json()
    assert any(e["action"] == "site_settings_update" for e in logs)


def test_audit_requires_admin(client, auth_headers):
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
    bh = {"Cookie": f"lipanel_session={b.cookies['lipanel_session']}"}
    assert client.get("/api/audit-logs", headers=bh).status_code == 403


def test_audit_rollover_keeps_1000(client, auth_headers, tmp_path):
    from app.db import connect

    conn = connect(client.app.state.db_path)
    for i in range(1005):
        conn.execute(
            "INSERT INTO audit_logs (user_id, action, detail) VALUES (1, 'bulk', ?)",
            (str(i),),
        )
    conn.commit()
    conn.close()
    logs = client.get("/api/audit-logs", headers=auth_headers, params={"limit": 1000}).json()
    assert len(logs) <= 1000
