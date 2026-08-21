def test_security_headers(client):
    r = client.get("/")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cross-origin-opener-policy"] == "same-origin"
    assert r.headers["cross-origin-resource-policy"] == "same-origin"
    assert "camera=()" in r.headers["permissions-policy"]
    csp = r.headers["content-security-policy"]
    assert "font-src 'self' data:" in csp
    assert "strict-transport-security" not in r.headers


def test_hsts_when_enabled(tmp_path):
    from fastapi.testclient import TestClient

    from app.config import load_settings
    from app.main import create_app

    app = create_app(
        load_settings(
            overrides={"data_dir": str(tmp_path), "secret_key": "x", "hsts": True}
        )
    )
    r = TestClient(app).get("/")
    assert r.headers["strict-transport-security"] == "max-age=63072000; includeSubDomains"


def _csrf_client(tmp_path, host="testserver"):
    from fastapi.testclient import TestClient

    from app.config import load_settings
    from app.main import create_app

    app = create_app(
        load_settings(overrides={"data_dir": str(tmp_path), "secret_key": "x"})
    )
    return TestClient(app, headers={"Host": host})


def _post(client, origin):
    return client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "secret123"},
        headers={"Origin": origin},
    )


def test_csrf_origin_same_host_different_port_blocked(tmp_path):
    """上线前修复：CSRF Origin 校验比较完整 host+port，同 host 不同端口必须拒绝。"""
    c = _csrf_client(tmp_path, host="localhost:8000")
    assert _post(c, "http://localhost:8080").status_code == 403
    # 同 host 同端口放行（继续走认证逻辑，不应是 403）
    assert _post(c, "http://localhost:8000").status_code != 403


def test_csrf_origin_default_port_normalized(tmp_path):
    """HTTPS 部署下 Host 带 :443、Origin 不带端口，仍应放行。"""
    c = _csrf_client(tmp_path, host="panel.example:443")
    assert _post(c, "https://panel.example").status_code != 403
    assert _post(c, "https://panel.example:443").status_code != 403


def test_csrf_origin_cross_host_blocked(tmp_path):
    c = _csrf_client(tmp_path, host="panel.example")
    assert _post(c, "http://evil.example").status_code == 403
    assert _post(c, "https://panel.example").status_code != 403
