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
