from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_JWK = json.loads(RSAAlgorithm.to_jwk(PRIVATE_KEY.public_key()))
PUBLIC_JWK["kid"] = "test-key"
KID = "test-key"

EVENT = "http://schemas.openid.net/event/backchannel-logout"


class _IssuerHandler(BaseHTTPRequestHandler):
    port = 0

    def do_GET(self):  # noqa: N802
        if self.path.endswith("openid-configuration"):
            body = json.dumps(
                {
                    "issuer": f"http://127.0.0.1:{self.port}",
                    "jwks_uri": f"http://127.0.0.1:{self.port}/jwks",
                }
            ).encode()
        else:
            body = json.dumps({"keys": [PUBLIC_JWK]}).encode()
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
    _IssuerHandler.port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def _app_with(tmp_path, **overrides):
    from fastapi.testclient import TestClient

    from app.config import load_settings
    from app.main import create_app

    base = {
        "data_dir": str(tmp_path),
        "secret_key": "x",
        "oidc_enabled": True,
        "oidc_client_id": "cid",
        "oidc_client_secret": "secret",
        "oidc_redirect_uri": "http://localhost/cb",
    }
    base.update(overrides)
    app = create_app(load_settings(overrides=base))
    client = TestClient(app)
    client.post("/api/setup", json={"username": "admin", "password": "secret123"})
    return client


def _seed_session(client, token="t1", sid="sid-1", sub="sub-1"):
    from app.db import connect

    conn = connect(client.app.state.db_path)
    conn.execute(
        "INSERT INTO sso_identities (user_id, provider, subject, email) "
        "VALUES (1, 'lipass', ?, 'a@example.com')",
        (sub,),
    )
    expires = (datetime.now(timezone.utc) + timedelta(days=1)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    conn.execute(
        "INSERT INTO sessions (token, user_id, sso_sid, expires_at) VALUES (?, 1, ?, ?)",
        (token, sid, expires),
    )
    conn.commit()
    conn.close()


def _make_token(issuer, *, sub="sub-1", sid="sid-1", events=True, key=None):
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {
        "iss": issuer,
        "aud": "cid",
        "iat": now,
        "exp": now + 300,
        "sub": sub,
        "sid": sid,
    }
    if events:
        claims["events"] = {EVENT: {}}
    return jwt.encode(
        claims,
        key or PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": KID},
    )


def test_backchannel_valid_logout(tmp_path, issuer):
    client = _app_with(tmp_path, oidc_issuer=issuer)
    _seed_session(client)
    token = _make_token(issuer)
    r = client.post(
        "/auth/sso/backchannel",
        data={"logout_token": token},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    assert client.get(
        "/api/auth/me", headers={"Cookie": "lipanel_session=t1"}
    ).status_code == 401


def test_backchannel_invalid_signature(tmp_path, issuer):
    client = _app_with(tmp_path, oidc_issuer=issuer)
    _seed_session(client)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _make_token(issuer, key=other)
    r = client.post("/auth/sso/backchannel", data={"logout_token": token})
    assert r.status_code == 401
    assert client.get(
        "/api/auth/me", headers={"Cookie": "lipanel_session=t1"}
    ).status_code == 200


def test_backchannel_missing_event(tmp_path, issuer):
    client = _app_with(tmp_path, oidc_issuer=issuer)
    _seed_session(client)
    token = _make_token(issuer, events=False)
    r = client.post("/auth/sso/backchannel", data={"logout_token": token})
    assert r.status_code == 401


def test_backchannel_unknown_sid_idempotent(tmp_path, issuer):
    client = _app_with(tmp_path, oidc_issuer=issuer)
    _seed_session(client)
    token = _make_token(issuer, sid="sid-nope")
    r = client.post("/auth/sso/backchannel", data={"logout_token": token})
    assert r.status_code == 200
    assert client.get(
        "/api/auth/me", headers={"Cookie": "lipanel_session=t1"}
    ).status_code == 200


def test_backchannel_json_body(tmp_path, issuer):
    client = _app_with(tmp_path, oidc_issuer=issuer)
    _seed_session(client)
    token = _make_token(issuer)
    r = client.post(
        "/auth/sso/backchannel",
        json={"logout_token": token},
    )
    assert r.status_code == 200


def test_backchannel_missing_token(client, issuer):
    r = client.post("/auth/sso/backchannel", data={})
    assert r.status_code == 400
