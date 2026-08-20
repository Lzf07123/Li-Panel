def test_site_settings_public_and_update(client, auth_headers):
    r = client.get("/api/site-settings")
    assert r.json()["site_name"] == "Li&Panel"
    r2 = client.put(
        "/api/site-settings",
        json={"site_name": "我的面板", "slogan": "常用入口"},
        headers=auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["site_name"] == "我的面板"
    assert client.get("/api/site-settings").json()["site_name"] == "我的面板"


def test_site_settings_requires_login(client):
    assert client.put("/api/site-settings", json={"site_name": "x"}).status_code == 401


def test_upload_requires_login_and_whitelist(client, auth_headers):
    png = b"\x89PNG\r\n\x1a\n"
    client.post("/api/auth/logout")
    assert (
        client.post(
            "/api/uploads", files={"file": ("a.png", png, "image/png")}
        ).status_code
        == 401
    )
    client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )
    r = client.post("/api/uploads", files={"file": ("a.png", png, "image/png")})
    assert r.status_code == 200
    assert r.json()["url"].startswith("/uploads/")
    assert (
        client.post(
            "/api/uploads",
            files={"file": ("a.svg", b"<svg/>", "image/svg+xml")},
        ).status_code
        == 422
    )


def test_user_settings(client, auth_headers):
    assert client.put(
        "/api/settings", json={"theme": "dark", "link_mode": "wan"}, headers=auth_headers
    ).status_code == 200
    assert client.put(
        "/api/settings", json={"theme": "nope"}, headers=auth_headers
    ).status_code == 422
