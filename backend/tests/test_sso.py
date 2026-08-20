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
