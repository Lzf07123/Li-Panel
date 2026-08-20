from __future__ import annotations

import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

from app.config import Settings


class OIDCError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def generate_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


class OIDCClient:
    """Li&Pass OIDC 客户端：发现/授权/换码/userinfo/JWKS 与 id_token 校验。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = httpx.Client(timeout=10)
        self._discovery_cache: tuple[float, dict] | None = None
        self._jwks_cache: tuple[float, dict] | None = None

    def _require_oidc_config(self) -> None:
        if not (
            self.settings.oidc_issuer
            and self.settings.oidc_client_id
            and self.settings.oidc_redirect_uri
        ):
            raise OIDCError("misconfigured", "OIDC 未配置完整")

    def discover(self) -> dict:
        self._require_oidc_config()
        if self._discovery_cache and time.monotonic() - self._discovery_cache[0] < 3600:
            return self._discovery_cache[1]
        url = self.settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration"
        try:
            response = self._client.get(url)
        except httpx.HTTPError as exc:
            raise OIDCError("network", "无法连接身份提供商") from exc
        if response.status_code != 200:
            raise OIDCError("network", "发现文档获取失败")
        data = response.json()
        self._discovery_cache = (time.monotonic(), data)
        return data

    def authorize_url(self, state: str, nonce: str, challenge: str) -> str:
        discovery = self.discover()
        params = {
            "response_type": "code",
            "client_id": self.settings.oidc_client_id,
            "redirect_uri": self.settings.oidc_redirect_uri,
            "scope": "openid profile email",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return discovery["authorization_endpoint"] + "?" + urlencode(params)

    def exchange(self, code: str, verifier: str) -> dict:
        discovery = self.discover()
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.oidc_redirect_uri,
            "client_id": self.settings.oidc_client_id,
            "code_verifier": verifier,
        }
        if self.settings.oidc_client_secret:
            data["client_secret"] = self.settings.oidc_client_secret
        try:
            response = self._client.post(
                discovery["token_endpoint"],
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.HTTPError as exc:
            raise OIDCError("network", "令牌交换失败") from exc
        if response.status_code != 200:
            try:
                error = response.json().get("error", "invalid_grant")
            except Exception:
                error = "invalid_grant"
            raise OIDCError(error, "令牌交换失败")
        return response.json()

    def userinfo(self, access_token: str) -> dict:
        discovery = self.discover()
        try:
            response = self._client.get(
                discovery["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.HTTPError as exc:
            raise OIDCError("network", "userinfo 获取失败") from exc
        if response.status_code != 200:
            raise OIDCError("invalid_token", "userinfo 获取失败")
        return response.json()

    def jwks(self) -> dict:
        self._require_oidc_config()
        if self._jwks_cache and time.monotonic() - self._jwks_cache[0] < 600:
            return self._jwks_cache[1]
        discovery = self.discover()
        try:
            response = self._client.get(discovery["jwks_uri"])
        except httpx.HTTPError as exc:
            raise OIDCError("network", "JWKS 获取失败") from exc
        if response.status_code != 200:
            raise OIDCError("network", "JWKS 获取失败")
        data = response.json()
        self._jwks_cache = (time.monotonic(), data)
        return data

    def validate_logout_token(self, logout_token: str) -> dict:
        """回程登出令牌校验：验签 + iss/aud/exp + backchannel-logout 事件。"""
        jwks = self.jwks()
        try:
            headers = jwt.get_unverified_header(logout_token)
            kid = headers.get("kid")
            key = None
            for jwk in jwks.get("keys", []):
                if jwk.get("kid") == kid:
                    key = RSAAlgorithm.from_jwk(jwk)
                    break
            if key is None:
                raise OIDCError("invalid_token", "找不到匹配的 JWKS 公钥")
            claims = jwt.decode(
                logout_token,
                key=key,
                algorithms=["RS256"],
                audience=self.settings.oidc_client_id,
                issuer=self.settings.oidc_issuer,
                options={"require": ["exp", "iss", "aud", "events"]},
            )
        except jwt.PyJWTError as exc:
            raise OIDCError("invalid_token", f"logout_token 校验失败: {exc}") from exc
        if "http://schemas.openid.net/event/backchannel-logout" not in (
            claims.get("events") or {}
        ):
            raise OIDCError("invalid_token", "缺少 backchannel-logout 事件")
        return claims

    def validate_id_token(
        self, id_token: str, nonce: str, access_token: str, jwks: dict
    ) -> dict:
        headers = jwt.get_unverified_header(id_token)
        kid = headers.get("kid")
        key = None
        for jwk in jwks.get("keys", []):
            if jwk.get("kid") == kid:
                key = RSAAlgorithm.from_jwk(jwk)
                break
        if key is None:
            raise OIDCError("invalid_token", "找不到匹配的 JWKS 公钥")
        try:
            claims = jwt.decode(
                id_token,
                key=key,
                algorithms=["RS256"],
                audience=self.settings.oidc_client_id,
                issuer=self.settings.oidc_issuer,
                options={"require": ["exp", "iat", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise OIDCError("invalid_token", f"id_token 校验失败: {exc}") from exc
        if claims.get("nonce") != nonce:
            raise OIDCError("invalid_token", "nonce 不一致")
        at_hash = (
            base64.urlsafe_b64encode(
                hashlib.sha256(access_token.encode()).digest()[:16]
            )
            .rstrip(b"=")
            .decode()
        )
        if claims.get("at_hash") != at_hash:
            raise OIDCError("invalid_token", "at_hash 校验失败")
        return claims
