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
    public_mode: bool
    cookie_secure: bool
    session_days: int
    oidc_enabled: bool
    oidc_issuer: str | None
    oidc_client_id: str | None
    oidc_client_secret: str | None
    oidc_redirect_uri: str | None

    @property
    def db_path(self) -> Path:
        return self.data_dir / "panel.db"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"


def load_settings(overrides: dict | None = None) -> Settings:
    """从环境变量读取配置；`overrides` 仅供测试注入。"""
    o = overrides or {}

    def get(key: str, default: str | None = None) -> str | None:
        if key in o:
            value = o[key]
            return None if value is None else str(value)
        return os.getenv(key, default)

    data_dir = Path(get("data_dir") or os.getenv("PANEL_DATA_DIR", "./data"))
    secret_key = get("secret_key") or os.getenv("PANEL_SECRET_KEY") or "dev-secret-change-me"
    return Settings(
        data_dir=data_dir,
        secret_key=secret_key,
        public_mode=_env_bool("PANEL_PUBLIC_MODE", True),
        cookie_secure=_env_bool("PANEL_COOKIE_SECURE", False),
        session_days=_env_int("PANEL_SESSION_DAYS", 30),
        oidc_enabled=_env_bool("OIDC_ENABLED", False),
        oidc_issuer=get("oidc_issuer") or os.getenv("OIDC_ISSUER"),
        oidc_client_id=get("oidc_client_id") or os.getenv("OIDC_CLIENT_ID"),
        oidc_client_secret=get("oidc_client_secret") or os.getenv("OIDC_CLIENT_SECRET"),
        oidc_redirect_uri=get("oidc_redirect_uri") or os.getenv("OIDC_REDIRECT_URI"),
    )
