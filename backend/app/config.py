from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    secret_key: str
    environment: str
    public_mode: bool
    cookie_secure: bool
    session_days: int
    oidc_enabled: bool
    oidc_issuer: str | None
    oidc_client_id: str | None
    oidc_client_secret: str | None
    oidc_redirect_uri: str | None
    link_icon_fetch: bool

    @property
    def db_path(self) -> Path:
        return self.data_dir / "panel.db"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"


def load_settings(overrides: dict | None = None) -> Settings:
    """从环境变量读取配置；`overrides` 仅供测试注入。"""
    o = overrides or {}

    def val(name: str, env: str, default: str | None) -> str | None:
        if name in o:
            value = o[name]
            return None if value is None else str(value)
        return os.getenv(env, default)

    def flag(name: str, env: str, default: bool) -> bool:
        if name in o:
            value = o[name]
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "true", "yes", "on"}
        return _env_bool(env, default)

    data_dir = Path(val("data_dir", "PANEL_DATA_DIR", "./data") or "./data")
    secret_key = val("secret_key", "PANEL_SECRET_KEY", "dev-secret-change-me") or "dev-secret-change-me"
    return Settings(
        data_dir=data_dir,
        secret_key=secret_key,
        environment=val("environment", "ENVIRONMENT", "development") or "development",
        public_mode=flag("public_mode", "PANEL_PUBLIC_MODE", True),
        cookie_secure=flag("cookie_secure", "PANEL_COOKIE_SECURE", False),
        session_days=_env_int("PANEL_SESSION_DAYS", 30)
        if "session_days" not in o
        else int(o["session_days"]),
        oidc_enabled=flag("oidc_enabled", "OIDC_ENABLED", False),
        oidc_issuer=val("oidc_issuer", "OIDC_ISSUER", None),
        oidc_client_id=val("oidc_client_id", "OIDC_CLIENT_ID", None),
        oidc_client_secret=val("oidc_client_secret", "OIDC_CLIENT_SECRET", None),
        oidc_redirect_uri=val("oidc_redirect_uri", "OIDC_REDIRECT_URI", None),
        link_icon_fetch=flag("link_icon_fetch", "PANEL_LINK_ICON_FETCH", True),
    )
