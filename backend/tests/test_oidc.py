import base64
import hashlib
import json
import time

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.config import load_settings
from app.oidc import OIDCClient, OIDCError, generate_pkce

ISSUER = "https://auth.example.com"
CLIENT_ID = "client1"


@pytest.fixture
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def jwks(rsa_key):
    jwk = json.loads(RSAAlgorithm.to_jwk(rsa_key.public_key()))
    jwk.update({"kid": "k1", "alg": "RS256", "use": "sig"})
    return {"keys": [jwk]}


def make_id_token(
    key, nonce="n1", at_hash="", **extra
) -> str:
    now = int(time.time())
    payload = {
        "iss": ISSUER,
        "sub": "u1",
        "aud": CLIENT_ID,
        "nonce": nonce,
        "iat": now,
        "exp": now + 300,
        "at_hash": at_hash,
        "sid": "s1",
    }
    payload.update(extra)
    return pyjwt.encode(payload, key, algorithm="RS256", headers={"kid": "k1"})


def test_generate_pkce():
    verifier, challenge = generate_pkce()
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert challenge == expected


def test_validate_id_token_ok(rsa_key, jwks):
    access_token = "access-token-123"
    at_hash = (
        base64.urlsafe_b64encode(hashlib.sha256(access_token.encode()).digest()[:16])
        .rstrip(b"=")
        .decode()
    )
    token = make_id_token(rsa_key, at_hash=at_hash)
    settings = load_settings(
        overrides={"oidc_issuer": ISSUER, "oidc_client_id": CLIENT_ID}
    )
    claims = OIDCClient(settings).validate_id_token(token, "n1", access_token, jwks)
    assert claims["sub"] == "u1"
    assert claims["sid"] == "s1"


def test_validate_id_token_nonce_mismatch(rsa_key, jwks):
    token = make_id_token(rsa_key, at_hash="x")
    settings = load_settings(
        overrides={"oidc_issuer": ISSUER, "oidc_client_id": CLIENT_ID}
    )
    with pytest.raises(OIDCError) as exc:
        OIDCClient(settings).validate_id_token(token, "wrong-nonce", "at", jwks)
    assert exc.value.code == "invalid_token"


def test_validate_id_token_at_hash_mismatch(rsa_key, jwks):
    token = make_id_token(rsa_key, at_hash="AAAAAAAAAAAAAAAAAAAAAA")
    settings = load_settings(
        overrides={"oidc_issuer": ISSUER, "oidc_client_id": CLIENT_ID}
    )
    with pytest.raises(OIDCError):
        OIDCClient(settings).validate_id_token(token, "n1", "at", jwks)


def test_validate_id_token_unknown_kid(rsa_key, jwks):
    token = make_id_token(rsa_key, at_hash="x")
    settings = load_settings(
        overrides={"oidc_issuer": ISSUER, "oidc_client_id": CLIENT_ID}
    )
    with pytest.raises(OIDCError):
        OIDCClient(settings).validate_id_token(
            token, "n1", "at", {"keys": [{"kid": "other"}]}
        )


def test_authorize_url_uses_discovery(monkeypatch):
    settings = load_settings(
        overrides={
            "oidc_issuer": ISSUER,
            "oidc_client_id": CLIENT_ID,
            "oidc_redirect_uri": "http://localhost/auth/sso/callback",
        }
    )
    client = OIDCClient(settings)
    monkeypatch.setattr(
        client,
        "discover",
        lambda: {"authorization_endpoint": f"{ISSUER}/oauth2/authorize"},
    )
    url = client.authorize_url("st", "nn", "ch")
    assert "response_type=code" in url
    assert "code_challenge=ch" in url
    assert "code_challenge_method=S256" in url
    assert "state=st" in url and "nonce=nn" in url
    assert "scope=openid+profile+email" in url
