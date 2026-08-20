from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 32


class _Handler(BaseHTTPRequestHandler):
    mode = "ok"

    def do_GET(self):  # noqa: N802
        if self.mode == "error":
            self.send_response(404)
            self.end_headers()
            return
        if self.path == "/favicon.ico":
            body = PNG_BYTES
            ctype = "image/png"
        else:
            body = (
                b'<html><head><link rel="icon" href="/favicon.ico"></head></html>'
            )
            ctype = "text/html"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # noqa: D102
        pass


@pytest.fixture(autouse=True)
def _clear_favicon_cache():
    from app import favicon as favicon_module

    with favicon_module._cache_lock:
        favicon_module._cache.clear()
    yield


@pytest.fixture
def icon_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_fetch_icon_success(client, auth_headers, icon_server):
    lid = client.post(
        "/api/links",
        json={"name": "站点", "url_lan": icon_server},
        headers=auth_headers,
    ).json()["id"]
    r = client.post(f"/api/links/{lid}/fetch-icon", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["icon_type"] == "upload"
    assert body["icon_value"].startswith("/favicons/link-")
    icon = client.get(body["icon_value"])
    assert icon.status_code == 200
    assert icon.headers["content-type"].startswith("image/")


def test_fetch_icon_no_icon(client, auth_headers, icon_server):
    _Handler.mode = "error"
    lid = client.post(
        "/api/links",
        json={"name": "站点", "url_lan": icon_server},
        headers=auth_headers,
    ).json()["id"]
    r = client.post(f"/api/links/{lid}/fetch-icon", headers=auth_headers)
    assert r.status_code == 404
    _Handler.mode = "ok"


def test_fetch_icon_disabled(client, icon_server, tmp_path):
    from fastapi.testclient import TestClient

    from app.config import load_settings
    from app.main import create_app

    app = create_app(
        load_settings(
            overrides={
                "data_dir": str(tmp_path),
                "secret_key": "x",
                "link_icon_fetch": False,
            }
        )
    )
    c = TestClient(app)
    c.post("/api/setup", json={"username": "admin", "password": "secret123"})
    login = c.post("/api/auth/login", json={"username": "admin", "password": "secret123"})
    headers = {"Cookie": f"lipanel_session={login.cookies['lipanel_session']}"}
    lid = c.post(
        "/api/links",
        json={"name": "站点", "url_lan": icon_server},
        headers=headers,
    ).json()["id"]
    assert c.post(f"/api/links/{lid}/fetch-icon", headers=headers).status_code == 400


def test_fetch_icon_foreign_404(client, auth_headers, icon_server):
    from app.db import connect
    from app.security import hash_password

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
    lid = client.post(
        "/api/links",
        json={"name": "站点", "url_lan": icon_server},
        headers=auth_headers,
    ).json()["id"]
    assert client.post(f"/api/links/{lid}/fetch-icon", headers=bh).status_code == 404


def test_favicon_route_missing_file_404(client):
    assert client.get("/favicons/does-not-exist.png").status_code == 404
    assert client.get("/favicons/..%2fsecret").status_code == 404


def test_auto_fetch_icon_on_create(client, auth_headers, icon_server):
    import time

    r = client.post(
        "/api/links",
        json={"name": "站点", "url_lan": icon_server},
        headers=auth_headers,
    )
    assert r.status_code == 201
    lid = r.json()["id"]
    icon = None
    for _ in range(30):
        links = client.get("/api/links", headers=auth_headers).json()
        link = next(l for l in links if l["id"] == lid)
        if link["icon_type"] == "upload":
            icon = link["icon_value"]
            break
        time.sleep(0.1)
    assert icon is not None and icon.startswith("/favicons/link-")
    assert client.get(icon).status_code == 200


def test_auto_fetch_skips_custom_icon(client, auth_headers, icon_server):
    import time

    r = client.post(
        "/api/links",
        json={
            "name": "站点",
            "url_lan": icon_server,
            "icon_type": "iconify",
            "icon_value": "mdi:test",
        },
        headers=auth_headers,
    )
    lid = r.json()["id"]
    time.sleep(0.5)
    links = client.get("/api/links", headers=auth_headers).json()
    link = next(l for l in links if l["id"] == lid)
    assert link["icon_type"] == "iconify"  # 不覆盖自定义图标


def test_auto_fetch_disabled(client, auth_headers, icon_server, tmp_path):
    import time
    from fastapi.testclient import TestClient

    from app.config import load_settings
    from app.main import create_app

    app = create_app(
        load_settings(
            overrides={
                "data_dir": str(tmp_path),
                "secret_key": "x",
                "link_icon_fetch": False,
            }
        )
    )
    c = TestClient(app)
    c.post("/api/setup", json={"username": "admin", "password": "secret123"})
    login = c.post("/api/auth/login", json={"username": "admin", "password": "secret123"})
    headers = {"Cookie": f"lipanel_session={login.cookies['lipanel_session']}"}
    lid = c.post(
        "/api/links",
        json={"name": "站点", "url_lan": icon_server},
        headers=headers,
    ).json()["id"]
    time.sleep(0.5)
    links = c.get("/api/links", headers=headers).json()
    link = next(l for l in links if l["id"] == lid)
    assert link["icon_type"] == "letter"  # 开关关闭时不自动抓取
