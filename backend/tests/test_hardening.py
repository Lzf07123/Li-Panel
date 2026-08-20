import io


def test_upload_magic_number_rejected(client, auth_headers):
    r = client.post(
        "/api/uploads",
        files={"file": ("fake.png", io.BytesIO(b"not an image"), "image/png")},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_upload_magic_number_ok(client, auth_headers):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    r = client.post(
        "/api/uploads",
        files={"file": ("real.png", io.BytesIO(png), "image/png")},
        headers=auth_headers,
    )
    assert r.status_code == 200


def test_secret_length_production(tmp_path):
    import pytest
    from fastapi.testclient import TestClient

    from app.config import load_settings
    from app.main import create_app

    with pytest.raises(RuntimeError):
        create_app(
            load_settings(
                overrides={
                    "data_dir": str(tmp_path),
                    "secret_key": "short",
                    "environment": "production",
                }
            )
        )
    # 足够长的密钥可启动
    app = create_app(
        load_settings(
            overrides={
                "data_dir": str(tmp_path),
                "secret_key": "x" * 40,
                "environment": "production",
            }
        )
    )
    assert TestClient(app).get("/api/health").status_code == 200


def test_host_cookie_prefix(client, tmp_path):
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
    assert "__Host-lipanel_session" in r.cookies
    headers = {"Cookie": f"__Host-lipanel_session={r.cookies['__Host-lipanel_session']}"}
    assert c.get("/api/auth/me", headers=headers).status_code == 200
    # 旧名不再可用
    old = {"Cookie": f"lipanel_session={r.cookies['__Host-lipanel_session']}"}
    assert c.get("/api/auth/me", headers=old).status_code == 401


def test_spa_fallback_traversal_blocked(client):
    """上线前修复：SPA 回退必须拒绝 .. 段，防止读取容器内任意文件（含 data/panel.db）。"""
    for path in [
        "/%2e%2e/%2e%2e/data/panel.db",
        "/..%2F..%2Fdata%2Fpanel.db",
        "/..%2F..%2Fbackend%2Fapp%2Fconfig.py",
        "/..%2f..%2fetc%2fpasswd",
        "/assets/..%2Fapp%2Fconfig.py",
    ]:
        r = client.get(path)
        assert r.status_code == 404, f"{path} 应返回 404，实际 {r.status_code}"


def test_spa_fallback_normal_paths_still_work(client):
    r = client.get("/")
    assert r.status_code == 200
    r = client.get("/login")
    assert r.status_code == 200
    r = client.get("/manifest.json")
    assert r.status_code == 200
