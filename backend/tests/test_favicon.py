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


class _SmartHandler(BaseHTTPRequestHandler):
    """可配置 HTML：mode=fallback 无 link 但有 /favicon.ico；mode=size 两个图标；mode=data 内联；mode=apple 仅 apple-touch。"""
    mode = "fallback"

    def do_GET(self):  # noqa: N802
        if self.path == "/favicon.ico" and self.mode == "fallback":
            body, ctype = PNG_BYTES, "image/png"
        elif self.mode == "size":
            if self.path == "/icon-16.png":
                body, ctype = PNG_BYTES, "image/png"
            elif self.path == "/icon-64.png":
                body, ctype = PNG_BYTES, "image/png"
            else:
                body = (
                    b'<html><head>'
                    b'<link rel="icon" href="/icon-16.png" sizes="16x16">'
                    b'<link rel="icon" href="/icon-64.png" sizes="64x64">'
                    b'</head></html>'
                )
                ctype = "text/html"
        elif self.mode == "data":
            import base64 as _b64

            data_uri = b"data:image/png;base64," + _b64.b64encode(PNG_BYTES)
            body = b"<html><head><link rel='icon' href='" + data_uri + b"'></head></html>"
            ctype = "text/html"
        elif self.mode == "apple":
            if self.path == "/apple.png":
                body, ctype = PNG_BYTES, "image/png"
            else:
                body = (
                    b'<html><head><link rel="apple-touch-icon" href="/apple.png"></head></html>'
                )
                ctype = "text/html"
        elif self.mode == "svg":
            body = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><circle cx="8" cy="8" r="8"/></svg>'
            ctype = "image/svg+xml"
        elif self.mode == "manifest":
            if self.path == "/manifest.json":
                import json as _json

                body = _json.dumps(
                    {
                        "name": "demo",
                        "icons": [
                            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
                            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                        ],
                    }
                ).encode()
                ctype = "application/manifest+json"
            elif self.path in ("/icon-192.png", "/icon-512.png"):
                body, ctype = PNG_BYTES, "image/png"
            else:
                body = b'<html><head><link rel="manifest" href="/manifest.json"></head></html>'
                ctype = "text/html"
        elif self.mode == "og":
            if self.path == "/og.png":
                body, ctype = PNG_BYTES, "image/png"
            else:
                body = b'<html><head><meta property="og:image" content="/og.png"></head></html>'
                ctype = "text/html"
        elif self.mode == "ms":
            if self.path == "/tile.png":
                body, ctype = PNG_BYTES, "image/png"
            else:
                body = b'<html><head><meta name="msapplication-TileImage" content="/tile.png"></head></html>'
                ctype = "text/html"
        elif self.mode == "rootpng":
            if self.path == "/favicon.png":
                body, ctype = PNG_BYTES, "image/png"
            else:
                body = b"<html><head></head></html>"
                ctype = "text/html"
        elif self.mode == "svgdata":
            body = (
                b"<html><head><link rel='icon' href='data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%3E%3C/svg%3E'></head></html>"
            )
            ctype = "text/html"
        else:
            body, ctype = PNG_BYTES, "image/png"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # noqa: D102
        pass


@pytest.fixture
def smart_server():
    _SmartHandler.mode = "fallback"
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SmartHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def _fetch_and_get_icon(client, auth_headers, url):
    lid = client.post(
        "/api/links", json={"name": "站点", "url_lan": url}, headers=auth_headers
    ).json()["id"]
    r = client.post(f"/api/links/{lid}/fetch-icon", headers=auth_headers)
    assert r.status_code == 200
    return r.json()["icon_value"]


def test_fallback_favicon_ico(client, auth_headers, smart_server):
    _SmartHandler.mode = "fallback"
    icon = _fetch_and_get_icon(client, auth_headers, smart_server)
    assert icon.endswith(".png")  # /favicon.ico 回退成功


def test_icon_size_preference(client, auth_headers, smart_server):
    _SmartHandler.mode = "size"
    # 请求 /icon-64.png 的路径会写进 /favicons 缓存文件名（无法直接看原路径），
    # 这里验证能抓到且内容为 PNG 即可；size 择优由单元级直接验证。
    icon = _fetch_and_get_icon(client, auth_headers, smart_server)
    assert client.get(icon).status_code == 200


def test_icon_size_preference_unit():
    from app.favicon import _pick_link_icon_url

    html = (
        '<html><head>'
        '<link rel="icon" href="/icon-16.png" sizes="16x16">'
        '<link rel="icon" href="/icon-64.png" sizes="64x64">'
        '</head></html>'
    )
    assert _pick_link_icon_url(html, "http://x.example/") == "http://x.example/icon-64.png"


def test_icon_base_href_unit():
    from app.favicon import _pick_link_icon_url

    html = '<html><head><base href="https://cdn.example/assets/"><link rel="icon" href="fav.png"></head></html>'
    assert _pick_link_icon_url(html, "http://x.example/") == "https://cdn.example/assets/fav.png"


def test_icon_data_uri(client, auth_headers, smart_server):
    _SmartHandler.mode = "data"
    icon = _fetch_and_get_icon(client, auth_headers, smart_server)
    assert client.get(icon).status_code == 200


def test_icon_apple_touch(client, auth_headers, smart_server):
    _SmartHandler.mode = "apple"
    icon = _fetch_and_get_icon(client, auth_headers, smart_server)
    assert client.get(icon).status_code == 200


def test_icon_svg_content_type(client, auth_headers, smart_server):
    _SmartHandler.mode = "svg"
    icon = _fetch_and_get_icon(client, auth_headers, smart_server)
    assert icon.endswith(".svg")
    resp = client.get(icon)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")


def test_manifest_icons(client, auth_headers, smart_server):
    _SmartHandler.mode = "manifest"
    icon = _fetch_and_get_icon(client, auth_headers, smart_server)
    assert client.get(icon).status_code == 200


def test_og_image_fallback(client, auth_headers, smart_server):
    _SmartHandler.mode = "og"
    icon = _fetch_and_get_icon(client, auth_headers, smart_server)
    assert client.get(icon).status_code == 200


def test_msapplication_tile(client, auth_headers, smart_server):
    _SmartHandler.mode = "ms"
    icon = _fetch_and_get_icon(client, auth_headers, smart_server)
    assert client.get(icon).status_code == 200


def test_root_favicon_png_fallback(client, auth_headers, smart_server):
    _SmartHandler.mode = "rootpng"
    icon = _fetch_and_get_icon(client, auth_headers, smart_server)
    assert client.get(icon).status_code == 200


def test_inline_svg_data_uri(client, auth_headers, smart_server):
    _SmartHandler.mode = "svgdata"
    icon = _fetch_and_get_icon(client, auth_headers, smart_server)
    assert icon.endswith(".svg")
    assert client.get(icon).status_code == 200


def test_size_first_scoring_unit():
    from app.favicon import _pick_link_icon_url

    html = (
        '<html><head>'
        '<link rel="apple-touch-icon" href="/apple-180.png" sizes="180x180">'
        '<link rel="icon" href="/icon-512.png" sizes="512x512">'
        '</head></html>'
    )
    assert _pick_link_icon_url(html, "http://x.example/") == "http://x.example/icon-512.png"
    html2 = (
        '<html><head>'
        '<link rel="apple-touch-icon" href="/apple-180.png" sizes="180x180">'
        '<link rel="icon" href="/icon-16.png" sizes="16x16">'
        '</head></html>'
    )
    assert _pick_link_icon_url(html2, "http://x.example/") == "http://x.example/apple-180.png"


def test_twitter_image_fallback(client, auth_headers, smart_server):
    _SmartHandler.mode = "twitter"
    # twitter 模式由当前 handler 未定义 → 走 og 分支同源，这里验证 meta 名采集单元
    from app.favicon import _candidate_urls

    html = '<html><head><meta name="twitter:image:src" content="/tw.png"></head></html>'
    candidates = _candidate_urls(html, "http://x.example/")
    assert any("tw.png" in c for c in candidates)
