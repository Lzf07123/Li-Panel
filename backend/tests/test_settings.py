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


def test_user_lang_roundtrip(client, auth_headers):
    r = client.put("/api/settings", json={"lang": "en-US"}, headers=auth_headers)
    assert r.status_code == 200
    assert client.get("/api/settings", headers=auth_headers).json()["lang"] == "en-US"
    r2 = client.put("/api/settings", json={"lang": "fr-FR"}, headers=auth_headers)
    assert r2.status_code == 422


def test_filing_settings_roundtrip(client, auth_headers):
    payload = {
        "icp": "浙ICP备20261234567号-1",
        "icp_url": "https://beian.miit.gov.cn/",
        "icp_icon": "/badges/icp.webp",
        "police_text": "浙公网安备 33010000012345 号",
        "police_url": "https://beian.mps.gov.cn/",
        "police_icon": "/badges/police.webp",
    }
    r = client.put("/api/site-settings", json=payload, headers=auth_headers)
    assert r.status_code == 200
    saved = r.json()
    assert saved["icp"] == payload["icp"]
    assert saved["police_text"] == payload["police_text"]
    assert saved["police_url"] == payload["police_url"]
    # 面板接口同样下发
    panel = client.get("/api/panel", headers=auth_headers).json()
    assert panel["site"]["icp"] == payload["icp"]
    assert panel["site"]["police_text"] == payload["police_text"]


def test_notify_url_admin_only(client, auth_headers):
    """上线前修复：通知 webhook 属敏感配置，仅管理员可见。"""
    r = client.put(
        "/api/site-settings",
        json={"notify_url": "https://hooks.example.com/secret", "notify_enabled": True},
        headers=auth_headers,
    )
    assert r.status_code == 200
    # 管理员可见
    r = client.get("/api/site-settings", headers=auth_headers)
    assert r.json()["notify_url"] == "https://hooks.example.com/secret"
    # 访客不可见（清空登录态 cookie jar）
    client.cookies.clear()
    r = client.get("/api/site-settings")
    assert "notify_url" not in r.json()
    assert "notify_enabled" not in r.json()
    # 访客面板也不下发
    r = client.get("/api/panel")
    assert "notify_url" not in r.json()["site"]
    assert "notify_enabled" not in r.json()["site"]
