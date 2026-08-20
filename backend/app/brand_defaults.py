from __future__ import annotations

import sqlite3

SITE_DEFAULTS: dict[str, str] = {
    "site_name": "Li&Panel",
    "slogan": "一次收藏，触达所有常用入口",
    "description": "",
    "logo": "/brand-logo.webp",
    "favicon": "/favicon.webp",
    "footer_text": "© 2026",
    "icp": "",
    "public_mode": "true",
    "notify_url": "",
    "notify_enabled": "false",
}


def seed_site_defaults(conn: sqlite3.Connection, public_mode_default: bool) -> None:
    defaults = dict(SITE_DEFAULTS)
    defaults["public_mode"] = "true" if public_mode_default else "false"
    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO site_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    conn.commit()


def get_site_settings(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM site_settings").fetchall()
    merged = dict(SITE_DEFAULTS)
    merged.update({row["key"]: row["value"] for row in rows})
    return merged
