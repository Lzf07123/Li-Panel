def test_security_headers(client):
    r = client.get("/")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cross-origin-opener-policy"] == "same-origin"
    assert r.headers["cross-origin-resource-policy"] == "same-origin"
    assert "camera=()" in r.headers["permissions-policy"]
    csp = r.headers["content-security-policy"]
    assert "font-src 'self' data:" in csp
    # 客户端存活探测：浏览器直连目标 URL（自动走系统/浏览器代理）
    assert "connect-src 'self' https: http:" in csp
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


def _post_headers(c, origin, extra=None):
    return c.post(
        "/api/auth/login",
        json={"username": "admin", "password": "secret123"},
        headers={"Origin": origin, **(extra or {})},
    )


def test_csrf_origin_nginx_no_forwarded_host_allows(tmp_path):
    """回归修复：nginx 默认 $host 剥离端口时，Host 无端口 + Origin 带端口必须放行。"""
    c = _csrf_client(tmp_path, host="119.130.239.18")
    assert _post_headers(c, "http://119.130.239.18:8000").status_code != 403


def test_csrf_origin_same_host_different_port_without_proxy_allows(tmp_path):
    """无 X-Forwarded-Host 时回退 hostname 比较（SameSite=Lax 兜底），不误伤反代部署。"""
    c = _csrf_client(tmp_path, host="localhost:8000")
    assert _post_headers(c, "http://localhost:8080").status_code != 403
    assert _post_headers(c, "http://localhost:8000").status_code != 403


def test_csrf_origin_x_forwarded_host_strict(tmp_path):
    """代理透传原始 Host（含端口）时，完整 netloc 严格校验：不同端口拒绝。"""
    c = _csrf_client(tmp_path, host="119.130.239.18")
    # 同 netloc → 放行
    r = _post_headers(
        c, "http://119.130.239.18:8000", {"X-Forwarded-Host": "119.130.239.18:8000"}
    )
    assert r.status_code != 403
    # 不同端口 → 拒绝
    r = _post_headers(
        c, "http://119.130.239.18:8080", {"X-Forwarded-Host": "119.130.239.18:8000"}
    )
    assert r.status_code == 403
    # 伪造 host → 拒绝
    r = _post_headers(
        c, "http://evil.example", {"X-Forwarded-Host": "119.130.239.18:8000"}
    )
    assert r.status_code == 403


def test_csrf_origin_default_port_normalized(tmp_path):
    """HTTPS 部署下 Host 带 :443、Origin 不带端口，仍应放行。"""
    c = _csrf_client(tmp_path, host="panel.example:443")
    assert _post_headers(c, "https://panel.example").status_code != 403
    assert _post_headers(c, "https://panel.example:443").status_code != 403


def test_csrf_origin_cross_host_blocked(tmp_path):
    c = _csrf_client(tmp_path, host="panel.example")
    assert _post_headers(c, "http://evil.example").status_code == 403
    assert _post_headers(c, "https://panel.example").status_code != 403
