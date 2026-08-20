def test_login_logout_me(client, admin):
    r = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )
    assert r.status_code == 200
    assert "lipanel_session" in r.headers["set-cookie"]
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "admin"
    assert me.json()["sso"]["bound"] is False
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_login_wrong_password(client, admin):
    r = client.post(
        "/api/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert r.status_code == 401
