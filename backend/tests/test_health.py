from __future__ import annotations

import threading
import time
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
def _clear_health_state():
    from app import health as health_module
    from app.routers import health as health_router

    with health_module._cache_lock:
        health_module._cache.clear()
    with health_router._inflight_lock:
        health_router._inflight.clear()
    yield


def _wait_for_posts(count: int, timeout: float = 3.0) -> int:
    """等待异步通知送达（通知改后台线程发送后，需轮询断言）。"""
    deadline = time.monotonic() + timeout
    while len(_NotifyHandler.posts) < count and time.monotonic() < deadline:
        time.sleep(0.01)
    return len(_NotifyHandler.posts)


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
    # icon_type=iconify 避免建链接触发后台 favicon 抓取打到同一测试服务器，
    # 否则其 GET /favicon.ico 会污染请求计数（与健康检查缓存无关的时序竞态）
    client.post(
        "/api/links",
        json={"name": "A", "url_lan": health_server, "icon_type": "iconify", "icon_value": "mdi:test"},
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


class _NotifyHandler(BaseHTTPRequestHandler):
    posts: list[dict] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        import json as _json

        body = _json.loads(self.rfile.read(length) or b"{}")
        _NotifyHandler.posts.append(body)
        self.send_response(200)
        self.end_headers()

    def do_GET(self):  # noqa: N802
        self._reply()

    def _reply(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):  # noqa: D102
        pass


@pytest.fixture
def notify_server():
    _NotifyHandler.posts = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _NotifyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/notify"
    server.shutdown()


def _set_notify(client, auth_headers, url, enabled=True):
    r = client.put(
        "/api/site-settings",
        json={"notify_url": url, "notify_enabled": enabled},
        headers=auth_headers,
    )
    assert r.status_code == 200


def test_notify_on_status_change(client, auth_headers, health_server, notify_server):
    from app import health as health_module
    from app.db import connect
    from datetime import datetime, timedelta, timezone

    _set_notify(client, auth_headers, notify_server)
    lid = client.post(
        "/api/links",
        json={"name": "A", "url_lan": health_server},
        headers=auth_headers,
    ).json()["id"]
    client.get("/api/health/links", headers=auth_headers)
    assert _wait_for_posts(1) == 1  # 首次采样视为状态变化

    def _reset_history(status):
        conn = connect(client.app.state.db_path)
        conn.execute("DELETE FROM link_health WHERE link_id = ?", (lid,))
        conn.execute(
            "INSERT INTO link_health (link_id, user_id, status, ms, checked_at) "
            "VALUES (?, 1, ?, 0, ?)",
            (lid, status, (datetime.now(timezone.utc) - timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        conn.close()

    # 同状态再次采样（绕过 10 分钟间隔与缓存）→ 不通知
    _reset_history("up")
    with health_module._cache_lock:
        health_module._cache.clear()
    client.get("/api/health/links", headers=auth_headers)
    time.sleep(0.1)  # 给异步通知留出到达窗口，确认没有多余通知
    assert len(_NotifyHandler.posts) == 1

    # 状态变化 → 通知
    REQUESTS["mode"] = "error"
    _reset_history("up")
    with health_module._cache_lock:
        health_module._cache.clear()
    client.get("/api/health/links", headers=auth_headers)
    assert _wait_for_posts(2) == 2
    assert _NotifyHandler.posts[-1]["status"] == "down"
    assert _NotifyHandler.posts[-1]["previous_status"] == "up"


def test_notify_disabled(client, auth_headers, health_server, notify_server):
    _set_notify(client, auth_headers, notify_server, enabled=False)
    client.post(
        "/api/links",
        json={"name": "A", "url_lan": health_server},
        headers=auth_headers,
    )
    client.get("/api/health/links", headers=auth_headers)
    time.sleep(0.1)  # 给异步通知留出到达窗口，确认没有通知发出
    assert _NotifyHandler.posts == []


def test_notify_failure_ignored(client, auth_headers, health_server):
    _set_notify(client, auth_headers, "http://127.0.0.1:1/nope")
    client.post(
        "/api/links",
        json={"name": "A", "url_lan": health_server},
        headers=auth_headers,
    )
    r = client.get("/api/health/links", headers=auth_headers)
    assert r.status_code == 200


def test_health_disabled_link_excluded(client, auth_headers, health_server):
    client.post(
        "/api/links",
        json={"name": "关", "url_lan": health_server, "health_enabled": False},
        headers=auth_headers,
    )
    client.post(
        "/api/links",
        json={"name": "开", "url_lan": health_server + "/on"},
        headers=auth_headers,
    )
    r = client.get("/api/health/links", headers=auth_headers).json()
    links = client.get("/api/links", headers=auth_headers).json()
    on_id = next(l["id"] for l in links if l["name"] == "开")
    off_id = next(l["id"] for l in links if l["name"] == "关")
    ids = [item["link_id"] for item in r["results"]]
    assert on_id in ids and off_id not in ids


def test_health_threshold(client, auth_headers, health_server):
    from app import health as health_module
    from app.db import connect
    from datetime import datetime, timedelta, timezone

    REQUESTS["mode"] = "error"
    lid = client.post(
        "/api/links",
        json={"name": "A", "url_lan": health_server, "health_threshold": 2},
        headers=auth_headers,
    ).json()["id"]

    def reset_history():
        conn = connect(client.app.state.db_path)
        conn.execute("DELETE FROM link_health WHERE link_id = ?", (lid,))
        conn.commit()
        conn.close()

    reset_history()
    with health_module._cache_lock:
        health_module._cache.clear()
    first = client.get("/api/health/links", headers=auth_headers).json()["results"][0]
    assert first["status"] == "up"  # 第 1 次失败未达阈值

    # 保留 fail_count=1 的旧采样，模拟跨轮次连续失败
    conn = connect(client.app.state.db_path)
    conn.execute(
        "INSERT INTO link_health (link_id, user_id, status, ms, fail_count, checked_at) "
        "VALUES (?, 1, 'up', 0, 1, ?)",
        (lid, (datetime.now(timezone.utc) - timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()
    with health_module._cache_lock:
        health_module._cache.clear()
    second = client.get("/api/health/links", headers=auth_headers).json()["results"][0]
    assert second["status"] == "down"  # 连续第 2 次失败达到阈值


def test_health_config_roundtrip(client, auth_headers, health_server):
    r = client.post(
        "/api/links",
        json={
            "name": "A",
            "url_lan": health_server,
            "health_interval": 30,
            "health_timeout": 3.0,
            "health_threshold": 3,
        },
        headers=auth_headers,
    )
    lid = r.json()["id"]
    assert r.json()["health_interval"] == 30
    assert r.json()["health_timeout"] == 3.0
    assert r.json()["health_threshold"] == 3
    r2 = client.put(
        f"/api/links/{lid}",
        json={"name": "A", "url_lan": health_server, "health_enabled": False},
        headers=auth_headers,
    )
    assert r2.json()["health_enabled"] == 0


def test_export_json(client, auth_headers, health_server):
    client.post(
        "/api/links",
        json={"name": "A", "url_lan": health_server},
        headers=auth_headers,
    )
    r = client.get("/api/health/export?format=json", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "A" and data[0]["status"] == "up"


def test_export_csv(client, auth_headers, health_server):
    client.post(
        "/api/links",
        json={"name": "A", "url_lan": health_server},
        headers=auth_headers,
    )
    r = client.get("/api/health/export?format=csv", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text.splitlines()[0] == "link_id,name,status,ms,checked_at"


def test_export_bad_format(client, auth_headers):
    assert (
        client.get("/api/health/export?format=xml", headers=auth_headers).status_code
        == 400
    )


def test_export_isolation(client, auth_headers, health_server):
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
    assert client.get("/api/health/export?format=json", headers=bh).json() == []


def test_health_refresh_bypasses_cache(client, auth_headers, health_server):
    from app import health as health_module

    client.post(
        "/api/links",
        json={"name": "A", "url_lan": health_server},
        headers=auth_headers,
    )
    client.get("/api/health/links", headers=auth_headers)
    first = REQUESTS["count"]
    client.get("/api/health/links", headers=auth_headers)
    assert REQUESTS["count"] == first  # 60s 缓存内不重复出站
    client.get("/api/health/links?refresh=1", headers=auth_headers)
    assert REQUESTS["count"] > first  # 用户侧强制刷新会重新检测


def test_allow_force_refresh_window():
    from app.routers import health as health_router

    with health_router._refresh_lock:
        health_router._refresh_last.clear()
    assert health_router._allow_force_refresh("k1") is True
    assert health_router._allow_force_refresh("k1") is False
    assert health_router._allow_force_refresh("k2") is True


def test_health_links_refresh_throttled(client, auth_headers, monkeypatch):
    """30s 窗口内第二次 refresh=1 不再强制出站检测（走缓存），防止焦点切换刷爆。"""
    from app.routers import health as health_router

    with health_router._refresh_lock:
        health_router._refresh_last.clear()

    lid = client.post(
        "/api/links",
        json={"name": "状态", "url_lan": "https://example.com"},
        headers=auth_headers,
    ).json()["id"]
    calls: list[str] = []

    def fake_check(url, timeout=5.0):
        calls.append(url)
        return "up", 12

    monkeypatch.setattr(health_router, "check_url", fake_check)

    r1 = client.get("/api/health/links?refresh=1", headers=auth_headers)
    assert r1.status_code == 200
    assert len(calls) == 1
    assert r1.json()["results"][0]["status"] == "up"

    # 30s 窗口内再次 refresh=1：节流降级，命中 60s 缓存，不再出站
    r2 = client.get("/api/health/links?refresh=1", headers=auth_headers)
    assert r2.status_code == 200
    assert len(calls) == 1, "第二次 refresh=1 不应再强制检测"
    assert r2.json()["results"][0]["link_id"] == lid


def test_single_flight_coalesces_concurrent_checks(monkeypatch):
    """同一链接的并发探测合并为一次出站（多标签页/并行请求共享结果）。"""
    from app.routers import health as health_router

    calls: dict[str, int] = {}
    barrier = threading.Barrier(2)

    def fake_check(url, timeout=5.0):
        calls[url] = calls.get(url, 0) + 1
        time.sleep(0.2)
        return "up", 10

    monkeypatch.setattr(health_router, "check_url", fake_check)

    link = {
        "id": 4242,
        "url_lan": "https://example.com/single-flight",
        "url_wan": None,
        "health_timeout": 5.0,
    }
    outcomes: list[list] = []

    def worker():
        barrier.wait()
        outcomes.append(health_router._check_many([link], refresh=True))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(calls) == 1, "并发探测同一链接只应出站一次"
    assert len(outcomes) == 2
    assert all(r[0]["status"] == "up" for r in outcomes)


def test_health_db_failure_503(client, monkeypatch):
    """/api/health 在数据库不可用时返回 503，让容器 healthcheck 感知。"""
    import sqlite3

    import app.main as main_module

    def boom(*args, **kwargs):
        raise sqlite3.OperationalError("db gone")

    monkeypatch.setattr(main_module, "connect", boom)
    r = client.get("/api/health")
    assert r.status_code == 503
    assert r.json()["status"] == "error"
