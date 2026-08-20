from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

REQUESTS = {"count": 0, "mode": "ok"}


class _Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):  # noqa: N802
        self._reply()

    def do_GET(self):  # noqa: N802
        self._reply()

    def _reply(self):
        REQUESTS["count"] += 1
        if REQUESTS["mode"] == "ok":
            self.send_response(200)
        elif REQUESTS["mode"] == "error":
            self.send_response(500)
        else:
            self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):  # noqa: D102
        pass


@pytest.fixture
def health_server():
    REQUESTS["count"] = 0
    REQUESTS["mode"] = "ok"
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(autouse=True)
def _clear_health_cache():
    from app import health as health_module

    with health_module._cache_lock:
        health_module._cache.clear()
    yield


def test_health_links_up(client, auth_headers, health_server):
    client.post(
        "/api/links",
        json={"name": "A", "url_lan": health_server},
        headers=auth_headers,
    )
    r = client.get("/api/health/links", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["enabled"] is True
    result = r.json()["results"][0]
    assert result["status"] == "up"
    assert result["ms"] >= 0


def test_health_links_down(client, auth_headers, health_server):
    REQUESTS["mode"] = "error"
    client.post(
        "/api/links",
        json={"name": "A", "url_lan": health_server},
        headers=auth_headers,
    )
    r = client.get("/api/health/links", headers=auth_headers)
    assert r.json()["results"][0]["status"] == "down"


def test_health_cache_avoids_refetch(client, auth_headers, health_server):
    client.post(
        "/api/links",
        json={"name": "A", "url_lan": health_server},
        headers=auth_headers,
    )
    client.get("/api/health/links", headers=auth_headers)
    count_after_first = REQUESTS["count"]
    client.get("/api/health/links", headers=auth_headers)
    assert REQUESTS["count"] == count_after_first


def test_health_disabled(client, auth_headers, health_server, tmp_path):
    from fastapi.testclient import TestClient

    from app.config import load_settings
    from app.main import create_app

    app = create_app(
        load_settings(
            overrides={
                "data_dir": str(tmp_path),
                "secret_key": "x",
                "health_check": False,
            }
        )
    )
    c = TestClient(app)
    c.post("/api/setup", json={"username": "admin", "password": "secret123"})
    login = c.post("/api/auth/login", json={"username": "admin", "password": "secret123"})
    headers = {"Cookie": f"lipanel_session={login.cookies['lipanel_session']}"}
    r = c.get("/api/health/links", headers=headers)
    assert r.json() == {"enabled": False, "results": []}


def test_health_isolation(client, auth_headers, health_server):
    from app.db import connect
    from app.security import hash_password

    client.post(
        "/api/links",
        json={"name": "A", "url_lan": health_server},
        headers=auth_headers,
    )
    conn = connect(client.app.state.db_path)
    ph, salt = hash_password("secret123")
    conn.execute(
        "INSERT INTO users (username, password_hash, salt, role) VALUES ('user_b', ?, ?, 'user')",
        (ph, salt),
    )
    conn.commit()
    conn.close()
    b = client.post(
        "/api/auth/login", json={"username": "user_b", "password": "secret123"}
    )
    bh = {"Cookie": f"lipanel_session={b.cookies['lipanel_session']}"}
    r = client.get("/api/health/links", headers=bh)
    assert r.json()["results"] == []


def test_health_requires_auth(client):
    assert client.get("/api/health/links").status_code == 401
