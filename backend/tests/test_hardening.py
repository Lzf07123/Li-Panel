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
