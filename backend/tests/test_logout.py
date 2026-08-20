from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


class _IssuerHandler(BaseHTTPRequestHandler):
    server_port = 0

    def do_GET(self):  # noqa: N802
        body = json.dumps(
            {"end_session_endpoint": f"http://127.0.0.1:{self.server_port}/endsession"}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # noqa: D102
        pass


@pytest.fixture
def issuer():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _IssuerHandler)
    _IssuerHandler.server_port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def _app_with(tmp_path, **overrides):
    from fastapi.testclient import TestClient

    from app.config import load_settings
    from app.main import create_app

    base = {"data_dir": str(tmp_path), "secret_key": "x"}
    base.update(overrides)
    app = create_app(load_settings(overrides=base))
    client = TestClient(app)
    client.post("/api/setup", json={"username": "admin", "password": "secret123"})
    return client


def test_sso_logout_local_only(client, auth_headers):
    r = client.get("/auth/sso/logout", headers=auth_headers, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/"
    assert client.get("/api/auth/me", headers=auth_headers).status_code == 401


def test_sso_logout_redirect_whitelist(tmp_path):
    client = _app_with(
        tmp_path, sso_logout_redirects=("https://allowed.example/",)
    )
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )
    headers = {"Cookie": f"lipanel_session={login.cookies['lipanel_session']}"}
    ok = client.get(
        "/auth/sso/logout",
        params={"redirect_after": "https://allowed.example/"},
        headers=headers,
        follow_redirects=False,
    )
    assert ok.status_code == 302
    assert ok.headers["location"] == "https://allowed.example/"

    login2 = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )
    headers2 = {"Cookie": f"lipanel_session={login2.cookies['lipanel_session']}"}
    bad = client.get(
        "/auth/sso/logout",
        params={"redirect_after": "https://evil.example/"},
        headers=headers2,
        follow_redirects=False,
    )
    assert bad.headers["location"] == "/"


def test_sso_logout_idp_redirect(tmp_path, issuer):
    client = _app_with(
        tmp_path,
        oidc_enabled=True,
        oidc_issuer=issuer,
        oidc_client_id="cid",
        oidc_client_secret="secret",
        oidc_redirect_uri="http://localhost/callback",
    )
    from app.db import connect

    conn = connect(client.app.state.db_path)
    expires = (datetime.now(timezone.utc) + timedelta(days=1)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    conn.execute(
        "INSERT INTO sessions (token, user_id, sso_id_token, expires_at) "
        "VALUES ('logout-token', 1, 'FAKE_ID_TOKEN', ?)",
        (expires,),
    )
    conn.commit()
    conn.close()
    headers = {"Cookie": "lipanel_session=logout-token"}
    r = client.get("/auth/sso/logout", headers=headers, follow_redirects=False)
    assert r.status_code == 302
    location = r.headers["location"]
    assert location.startswith(f"{issuer}/endsession?")
    assert "id_token_hint=FAKE_ID_TOKEN" in location
    assert "post_logout_redirect_uri=%2F" in location
