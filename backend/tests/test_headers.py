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
