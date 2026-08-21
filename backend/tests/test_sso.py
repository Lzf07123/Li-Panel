from urllib.parse import parse_qs, unquote, urlparse

import pytest

from app import oidc as oidc_mod
from app.config import load_settings
from app.main import create_app

ISSUER = "https://auth.example.com"


class FakeOIDCClient:
    def __init__(self, settings):
        self.settings = settings

    def discover(self):
        return {"authorization_endpoint": f"{ISSUER}/oauth2/authorize"}

    def authorize_url(self, state, nonce, challenge):
        return f"{ISSUER}/oauth2/authorize?state={state}"

    def exchange(self, code, verifier):
        return {"access_token": "at", "id_token": "idt"}

    def userinfo(self, access_token):
        return {"sub": "u1", "email": "alice@example.com", "nickname": "Alice"}

    def jwks(self):
        return {"keys": []}

    def validate_id_token(self, id_token, nonce, access_token, jwks):
        return {"sub": "u1", "sid": "s1"}


@pytest.fixture
def sso_client(tmp_path, monkeypatch):
    monkeypatch.setattr(oidc_mod, "OIDCClient", FakeOIDCClient)
    settings = load_settings(
        overrides={
            "data_dir": str(tmp_path),
            "secret_key": "test",
            "public_mode": True,
            "oidc_enabled": True,
            "oidc_issuer": ISSUER,
            "oidc_client_id": "client1",
            "oidc_redirect_uri": "http://testserver/auth/sso/callback",
        }
    )
    client = create_app(settings)
    test_client = pytest.importorskip("fastapi.testclient").TestClient(client)
    assert (
        test_client.post(
            "/api/setup", json={"username": "admin", "password": "secret123"}
        ).status_code
        == 201
    )
    return test_client


def _start_flow(client) -> tuple[str, str]:
    r = client.get("/auth/sso/login", follow_redirects=False)
    assert r.status_code == 302
    flow_cookie = r.headers["set-cookie"].split(";")[0].split("=", 1)[1]
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    return flow_cookie, state


def test_sso_login_and_create_account(sso_client):
    flow_cookie, state = _start_flow(sso_client)
    cb = sso_client.get(
        f"/auth/sso/callback?code=code&state={state}",
        headers={"Cookie": f"lipanel_sso_flow={flow_cookie}"},
        follow_redirects=False,
    )
    assert cb.status_code == 302
    assert cb.headers["location"].endswith("/sso/link")
    r = sso_client.post(
        "/api/sso/link",
        json={"action": "create", "username": "alice", "password": "secret123"},
        headers={"Cookie": f"lipanel_sso_flow={flow_cookie}"},
    )
    assert r.status_code == 201
    assert "lipanel_session" in r.headers["set-cookie"]
    me = sso_client.get("/api/auth/me")
    assert me.json()["user"]["username"] == "alice"
    assert me.json()["sso"]["bound"] is True
    assert me.json()["sso"]["email"] == "alice@example.com"


def test_sso_bind_existing_account(sso_client):
    flow_cookie, state = _start_flow(sso_client)
    sso_client.get(
        f"/auth/sso/callback?code=code&state={state}",
        headers={"Cookie": f"lipanel_sso_flow={flow_cookie}"},
        follow_redirects=False,
    )
    bad = sso_client.post(
        "/api/sso/link",
        json={"action": "bind", "username": "admin", "password": "wrong"},
        headers={"Cookie": f"lipanel_sso_flow={flow_cookie}"},
    )
    assert bad.status_code == 401
    ok = sso_client.post(
        "/api/sso/link",
        json={"action": "bind", "username": "admin", "password": "secret123"},
        headers={"Cookie": f"lipanel_sso_flow={flow_cookie}"},
    )
    assert ok.status_code == 200
    me = sso_client.get("/api/auth/me")
    assert me.json()["user"]["username"] == "admin"
    assert me.json()["sso"]["bound"] is True


def test_sso_flow_cannot_reuse(sso_client):
    flow_cookie, state = _start_flow(sso_client)
    sso_client.get(
        f"/auth/sso/callback?code=code&state={state}",
        headers={"Cookie": f"lipanel_sso_flow={flow_cookie}"},
        follow_redirects=False,
    )
    r1 = sso_client.post(
        "/api/sso/link",
        json={"action": "create", "username": "alice", "password": "secret123"},
        headers={"Cookie": f"lipanel_sso_flow={flow_cookie}"},
    )
    assert r1.status_code == 201
    r2 = sso_client.post(
        "/api/sso/link",
        json={"action": "create", "username": "bob", "password": "secret123"},
        headers={"Cookie": f"lipanel_sso_flow={flow_cookie}"},
    )
    assert r2.status_code == 409


def test_sso_callback_state_mismatch(sso_client):
    flow_cookie, _ = _start_flow(sso_client)
    r = sso_client.get(
        "/auth/sso/callback?code=code&state=WRONG",
        headers={"Cookie": f"lipanel_sso_flow={flow_cookie}"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "error" in r.headers["location"]


def test_sso_callback_error_account_blocked(sso_client):
    r = sso_client.get(
        "/auth/sso/callback?error=access_denied&error_description=account_blocked",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "封禁" in unquote(r.headers["location"])


def test_logout_uri_safety(sso_client):
    r = sso_client.get("/auth/logout?next=//evil.com", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/"
    r2 = sso_client.get("/auth/logout?next=/settings", follow_redirects=False)
    assert r2.headers["location"] == "/settings"


def _bind_sso(client, user_id=1):
    from app.db import connect

    conn = connect(client.app.state.db_path)
    conn.execute(
        "INSERT INTO sso_identities (user_id, provider, subject, email, nickname) "
        "VALUES (?, 'lipass', 'sub-1', 'a@example.com', 'Alias')",
        (user_id,),
    )
    conn.commit()
    conn.close()


def test_sso_status_bound(client, auth_headers):
    _bind_sso(client)
    r = client.get("/api/sso/status", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == {
        "bound": True,
        "provider": "lipass",
        "email": "a@example.com",
        "nickname": "Alias",
    }


def test_sso_unbind_with_password(client, auth_headers):
    _bind_sso(client)
    r = client.request(
        "DELETE", "/api/sso/identity", json={"password": "secret123"}, headers=auth_headers
    )
    assert r.status_code == 200 and r.json() == {"ok": True}
    status = client.get("/api/sso/status", headers=auth_headers).json()
    assert status["bound"] is False
    # 本地账号仍在
    assert client.get("/api/auth/me", headers=auth_headers).status_code == 200


def test_sso_unbind_wrong_password(client, auth_headers):
    _bind_sso(client)
    r = client.request(
        "DELETE", "/api/sso/identity", json={"password": "wrong"}, headers=auth_headers
    )
    assert r.status_code == 403


def test_sso_unbind_not_bound(client, auth_headers):
    r = client.request(
        "DELETE", "/api/sso/identity", json={"password": "secret123"}, headers=auth_headers
    )
    assert r.status_code == 400


def test_sso_host_cookie_used_everywhere(tmp_path, monkeypatch):
    """上线前修复：开启 PANEL_HOST_COOKIE 后，SSO 回调/登出也必须使用 __Host- 前缀会话 Cookie。"""
    from fastapi.testclient import TestClient

    monkeypatch.setattr(oidc_mod, "OIDCClient", FakeOIDCClient)
    settings = load_settings(
        overrides={
            "data_dir": str(tmp_path),
            "secret_key": "test",
            "public_mode": True,
            "host_cookie": True,
            "cookie_secure": True,
            "oidc_enabled": True,
            "oidc_issuer": ISSUER,
            "oidc_client_id": "client1",
            "oidc_redirect_uri": "http://testserver/auth/sso/callback",
        }
    )
    c = TestClient(create_app(settings))
    assert c.post("/api/setup", json={"username": "admin", "password": "secret123"}).status_code == 201

    # 首次回调进入关联页
    flow_cookie, state = _start_flow(c)
    cb = c.get(
        f"/auth/sso/callback?code=code&state={state}",
        headers={"Cookie": f"lipanel_sso_flow={flow_cookie}"},
        follow_redirects=False,
    )
    assert cb.status_code == 302 and cb.headers["location"].endswith("/sso/link")
    # 绑定已有账号 → 会话 Cookie 使用 __Host- 前缀
    r = c.post(
        "/api/sso/link",
        json={"action": "bind", "username": "admin", "password": "secret123"},
        headers={"Cookie": f"lipanel_sso_flow={flow_cookie}"},
    )
    assert r.status_code == 200
    host_cookie = r.cookies["__Host-lipanel_session"]
    assert c.get("/api/auth/me", headers={"Cookie": f"__Host-lipanel_session={host_cookie}"}).status_code == 200
    assert c.get("/api/auth/me", headers={"Cookie": f"lipanel_session={host_cookie}"}).status_code == 401

    # 已绑定身份再次回调 → 自动登录也必须写 __Host- 前缀
    flow_cookie2, state2 = _start_flow(c)
    cb2 = c.get(
        f"/auth/sso/callback?code=code&state={state2}",
        headers={"Cookie": f"lipanel_sso_flow={flow_cookie2}"},
        follow_redirects=False,
    )
    assert cb2.status_code == 302
    assert "__Host-lipanel_session" in cb2.headers["set-cookie"]
    auto_cookie = cb2.cookies["__Host-lipanel_session"]
    assert c.get("/api/auth/me", headers={"Cookie": f"__Host-lipanel_session={auto_cookie}"}).status_code == 200

    # RP 发起登出按配置的 Cookie 名读取并注销会话
    r = c.get(
        "/auth/sso/logout",
        headers={"Cookie": f"__Host-lipanel_session={auto_cookie}"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert c.get("/api/auth/me", headers={"Cookie": f"__Host-lipanel_session={auto_cookie}"}).status_code == 401


def test_logout_uri_rejects_backslash(client):
    """上线前修复：next 含反斜杠一律回站内，防浏览器 \\→/ 规范化导致开放跳转。"""
    r = client.get("/auth/logout?next=/\\evil.example.com", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/"
    r = client.get("/auth/logout?next=//evil.example.com", follow_redirects=False)
    assert r.headers["location"] == "/"


def test_sso_login_rate_limited(sso_client):
    """上线前修复：SSO 发起入口与回调一致，按 IP 限流。"""
    locations = []
    for _ in range(11):
        r = sso_client.get("/auth/sso/login", follow_redirects=False)
        locations.append(r.headers.get("location", ""))
    assert locations[-1].startswith("/login?error="), locations[-1]
    assert "请求过于频繁" in unquote(locations[-1])


def test_sso_flow_cleanup(sso_client):
    """上线前修复：sso_flows 滚动清理过期与已消费（>1 天）流程。"""
    from datetime import datetime, timedelta, timezone

    from app.db import connect

    db_path = sso_client.app.state.db_path
    conn = connect(db_path)
    now = datetime.now(timezone.utc)
    fmt = lambda dt: dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    # 过期未消费 → 应删
    conn.execute(
        "INSERT INTO sso_flows (token, state, nonce, code_verifier, expires_at, consumed, created_at) "
        "VALUES ('expired-flow', 's', 'n', 'v', ?, 0, ?)",
        (fmt(now - timedelta(minutes=1)), fmt(now - timedelta(hours=2))),
    )
    # 已消费且超过 1 天 → 应删
    conn.execute(
        "INSERT INTO sso_flows (token, state, nonce, code_verifier, expires_at, consumed, created_at) "
        "VALUES ('old-consumed', 's', 'n', 'v', ?, 1, ?)",
        (fmt(now + timedelta(minutes=5)), fmt(now - timedelta(days=2))),
    )
    # 已消费但未超 1 天 → 保留
    conn.execute(
        "INSERT INTO sso_flows (token, state, nonce, code_verifier, expires_at, consumed, created_at) "
        "VALUES ('fresh-consumed', 's', 'n', 'v', ?, 1, ?)",
        (fmt(now + timedelta(minutes=5)), fmt(now - timedelta(minutes=30))),
    )
    conn.commit()
    conn.close()

    r = sso_client.get("/auth/sso/login", follow_redirects=False)
    assert r.status_code == 302

    conn = connect(db_path)
    tokens = [
        row["token"]
        for row in conn.execute("SELECT token FROM sso_flows").fetchall()
    ]
    conn.close()
    assert "expired-flow" not in tokens
    assert "old-consumed" not in tokens
    assert "fresh-consumed" in tokens
