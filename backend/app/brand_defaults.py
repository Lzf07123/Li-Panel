from __future__ import annotations

import sqlite3

SITE_DEFAULTS: dict[str, str] = {
    "site_name": "Li&Panel",
    "slogan": "一次收藏，触达所有常用入口",
    "description": "",
    "logo": "/brand-logo.webp",
    "favicon": "/favicon.webp",
    "footer_text": "",
    "copyright": "",  # 页脚版权行：留空时前端自动生成「© 年份 站点名 · v版本」
    # 旧版本曾把 "© 2026" 写入 footer_text，与前端固定版权行「© 年 品牌 · v版本」重复；
    # 现在默认留空，页脚版权只渲染一次，footer_text 仅承载自定义补充文案。
    "icp": "",
    "icp_url": "https://beian.miit.gov.cn/",
    "icp_icon": "/badges/icp.webp",
    "police_text": "",
    "police_url": "https://beian.mps.gov.cn/",
    "police_icon": "/badges/police.webp",
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
    # 迁移：清理旧版本遗留的重复版权值（等于旧默认 "© 2026" 时清空）
    conn.execute(
        "UPDATE site_settings SET value = '' "
        "WHERE key = 'footer_text' AND value = '© 2026'"
    )
    conn.commit()


def get_site_settings(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM site_settings").fetchall()
    merged = dict(SITE_DEFAULTS)
    merged.update({row["key"]: row["value"] for row in rows})
    return merged
