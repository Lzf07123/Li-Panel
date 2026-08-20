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


def test_history_records_sample(client, auth_headers, health_server):
    client.post(
        "/api/links",
        json={"name": "A", "url_lan": health_server},
        headers=auth_headers,
    )
    client.get("/api/health/links", headers=auth_headers)
    links = client.get("/api/links", headers=auth_headers).json()
    lid = links[0]["id"]
    history = client.get(f"/api/health/links/{lid}/history", headers=auth_headers)
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["status"] == "up"


def test_history_sample_interval_skips(client, auth_headers, health_server):
    from app import health as health_module

    client.post(
        "/api/links",
        json={"name": "A", "url_lan": health_server},
        headers=auth_headers,
    )
    client.get("/api/health/links", headers=auth_headers)
    with health_module._cache_lock:
        health_module._cache.clear()
    client.get("/api/health/links", headers=auth_headers)
    lid = client.get("/api/links", headers=auth_headers).json()[0]["id"]
    history = client.get(f"/api/health/links/{lid}/history", headers=auth_headers).json()
    assert len(history) == 1  # 10 分钟内不重复采样


def test_history_old_sample_inserts(client, auth_headers, health_server):
    from app import health as health_module
    from app.db import connect
    from datetime import datetime, timedelta, timezone

    lid = client.post(
        "/api/links",
        json={"name": "A", "url_lan": health_server},
        headers=auth_headers,
    ).json()["id"]
    conn = connect(client.app.state.db_path)
    old = (datetime.now(timezone.utc) - timedelta(minutes=20)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    conn.execute(
        "INSERT INTO link_health (link_id, user_id, status, ms, checked_at) "
        "VALUES (?, 1, 'down', 0, ?)",
        (lid, old),
    )
    conn.commit()
    conn.close()
    with health_module._cache_lock:
        health_module._cache.clear()
    client.get("/api/health/links", headers=auth_headers)
    history = client.get(f"/api/health/links/{lid}/history", headers=auth_headers).json()
    assert len(history) == 2


def test_history_foreign_404(client, auth_headers, health_server):
    from app.db import connect
    from app.security import hash_password

    lid = client.post(
        "/api/links",
        json={"name": "A", "url_lan": health_server},
        headers=auth_headers,
    ).json()["id"]
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
    assert client.get(f"/api/health/links/{lid}/history", headers=bh).status_code == 404


def test_public_status_only_public(client, auth_headers, health_server):
    client.post(
        "/api/links",
        json={"name": "公开", "url_lan": health_server, "is_public": True},
        headers=auth_headers,
    )
    client.post(
        "/api/links",
        json={"name": "私密", "url_lan": health_server + "/private", "is_public": False},
        headers=auth_headers,
    )
    r = client.get("/api/health/status")
    assert r.status_code == 200
    links = client.get("/api/links", headers=auth_headers).json()
    public_id = next(l["id"] for l in links if l["name"] == "公开")
    private_id = next(l["id"] for l in links if l["name"] == "私密")
    ids = [item["link_id"] for item in r.json()["results"]]
    assert public_id in ids and private_id not in ids


def test_public_status_respects_public_mode(client, auth_headers, health_server, tmp_path):
    from fastapi.testclient import TestClient

    from app.config import load_settings
    from app.main import create_app

    app = create_app(
        load_settings(
            overrides={"data_dir": str(tmp_path), "secret_key": "x", "public_mode": False}
        )
    )
    c = TestClient(app)
    assert c.get("/api/health/status").status_code == 401
