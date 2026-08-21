def _second_session(client):
    r = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )
    return {"Cookie": f"lipanel_session={r.cookies['lipanel_session']}"}


def test_list_sessions_marks_current(client, auth_headers):
    other = _second_session(client)
    sessions = client.get("/api/sessions", headers=auth_headers).json()
    assert len(sessions) == 2
    assert sum(1 for s in sessions if s["current"]) == 1


def test_revoke_other_session(client, auth_headers):
    other = _second_session(client)
    sessions = client.get("/api/sessions", headers=auth_headers).json()
    other_session = next(s for s in sessions if not s["current"])
    r = client.delete(
        f"/api/sessions/{other_session['id']}", headers=auth_headers
    )
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=other).status_code == 401
    assert client.get("/api/auth/me", headers=auth_headers).status_code == 200


def test_revoke_current_rejected(client, auth_headers):
    sessions = client.get("/api/sessions", headers=auth_headers).json()
    current = next(s for s in sessions if s["current"])
    assert (
        client.delete(f"/api/sessions/{current['id']}", headers=auth_headers).status_code
        == 400
    )


def test_revoke_all_keeps_current(client, auth_headers):
    other = _second_session(client)
    r = client.delete("/api/sessions", headers=auth_headers)
    assert r.status_code == 200 and r.json()["revoked"] == 1
    assert client.get("/api/auth/me", headers=other).status_code == 401
    assert client.get("/api/auth/me", headers=auth_headers).status_code == 200


def test_revoke_foreign_session_404(client, auth_headers):
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
    sessions = client.get("/api/sessions", headers=bh).json()
    assert (
        client.delete(f"/api/sessions/{sessions[0]['id']}", headers=auth_headers).status_code
        == 404
    )


def _host_cookie_client(tmp_path):
    from fastapi.testclient import TestClient

    from app.config import load_settings
    from app.main import create_app

    app = create_app(
        load_settings(
            overrides={
                "data_dir": str(tmp_path),
                "secret_key": "x",
                "host_cookie": True,
                "cookie_secure": True,
            }
        )
    )
    c = TestClient(app)
    c.post("/api/setup", json={"username": "admin", "password": "secret123"})
    r = c.post("/api/auth/login", json={"username": "admin", "password": "secret123"})
    return c, {"Cookie": f"__Host-lipanel_session={r.cookies['__Host-lipanel_session']}"}


def test_host_cookie_sessions_marks_current(tmp_path):
    """上线前修复：__Host- 会话模式下会话管理接口必须正确识别当前会话。"""
    c, headers = _host_cookie_client(tmp_path)
    sessions = c.get("/api/sessions", headers=headers).json()
    assert len(sessions) == 1
    assert sum(1 for s in sessions if s["current"]) == 1


def test_host_cookie_revoke_current_rejected(tmp_path):
    c, headers = _host_cookie_client(tmp_path)
    sessions = c.get("/api/sessions", headers=headers).json()
    current = next(s for s in sessions if s["current"])
    assert (
        c.delete(f"/api/sessions/{current['id']}", headers=headers).status_code == 400
    )
    assert c.get("/api/auth/me", headers=headers).status_code == 200


def test_host_cookie_revoke_all_keeps_current(tmp_path):
    c, headers = _host_cookie_client(tmp_path)
    r = c.delete("/api/sessions", headers=headers)
    assert r.status_code == 200 and r.json()["revoked"] == 0
    assert c.get("/api/auth/me", headers=headers).status_code == 200
