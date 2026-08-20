from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>示例</title>
<item><title>第一条</title><link>http://example.com/1</link><pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate><description>描述一</description></item>
<item><title>第二条</title><link>http://example.com/2</link></item>
</channel></rss>"""

REQUESTS = {"count": 0}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        REQUESTS["count"] += 1
        body = RSS_XML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/rss+xml")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # noqa: D102
        pass


@pytest.fixture
def rss_server():
    REQUESTS["count"] = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/feed.xml"
    server.shutdown()


@pytest.fixture(autouse=True)
def _clear_rss_cache():
    from app import rss as rss_module

    with rss_module._cache_lock:
        rss_module._cache.clear()
    yield


def test_rss_set_and_fetch(client, auth_headers, rss_server):
    r = client.put(
        "/api/settings", json={"rss_feeds": [rss_server]}, headers=auth_headers
    )
    assert r.status_code == 200
    feeds = client.get("/api/rss", headers=auth_headers).json()["feeds"]
    assert len(feeds) == 1
    items = feeds[0]["items"]
    assert [i["title"] for i in items] == ["第一条", "第二条"]
    assert items[0]["link"] == "http://example.com/1"


def test_rss_rejects_invalid_url(client, auth_headers):
    r = client.put(
        "/api/settings", json={"rss_feeds": ["ftp://bad"]}, headers=auth_headers
    )
    assert r.status_code == 400


def test_rss_max_three(client, auth_headers):
    r = client.put(
        "/api/settings",
        json={"rss_feeds": ["http://a.com", "http://b.com", "http://c.com", "http://d.com"]},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_rss_cache_avoids_refetch(client, auth_headers, rss_server):
    client.put("/api/settings", json={"rss_feeds": [rss_server]}, headers=auth_headers)
    client.get("/api/rss", headers=auth_headers)
    first = REQUESTS["count"]
    client.get("/api/rss", headers=auth_headers)
    assert REQUESTS["count"] == first


def test_rss_isolation(client, auth_headers, rss_server):
    from app.db import connect
    from app.security import hash_password

    client.put("/api/settings", json={"rss_feeds": [rss_server]}, headers=auth_headers)
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
    assert client.get("/api/rss", headers=bh).json()["feeds"] == []
