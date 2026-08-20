def _app_with(tmp_path, allowed_hosts):
    from fastapi.testclient import TestClient

    from app.config import load_settings
    from app.main import create_app

    app = create_app(
        load_settings(
            overrides={
                "data_dir": str(tmp_path),
                "secret_key": "x",
                "allowed_hosts": allowed_hosts,
            }
        )
    )
    return TestClient(app)


def test_allowed_host_exact(tmp_path):
    c = _app_with(tmp_path, ("panel.example",))
    assert c.get("/api/health", headers={"Host": "panel.example"}).status_code == 200
    assert c.get("/api/health", headers={"Host": "evil.example"}).status_code == 403


def test_allowed_host_wildcard(tmp_path):
    c = _app_with(tmp_path, ("*.example.com",))
    assert c.get("/api/health", headers={"Host": "a.example.com"}).status_code == 200
    assert c.get("/api/health", headers={"Host": "evil.org"}).status_code == 403


def test_allowed_hosts_empty_allow_all(tmp_path):
    c = _app_with(tmp_path, ())
    assert c.get("/api/health", headers={"Host": "whatever.example"}).status_code == 200
