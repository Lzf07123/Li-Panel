from __future__ import annotations

import json
import sqlite3
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.brand_defaults import get_site_settings
from app.db import get_db
from app.deps import current_user, optional_user

router = APIRouter(tags=["panel"])


def _effective_url(link: sqlite3.Row, mode: str) -> str:
    if mode == "wan":
        return link["url_wan"] or link["url_lan"]
    return link["url_lan"] or link["url_wan"]


def _public_link_dict(link: sqlite3.Row, show_url: bool) -> dict:
    data = {
        "id": link["id"],
        "name": link["name"],
        "icon_type": link["icon_type"],
        "icon_value": link["icon_value"],
        "description": link["description"],
        "open_mode": link["open_mode"],
        "tags": json.loads(link["tags"] or "[]"),
    }
    if show_url:
        data["url"] = _effective_url(link, "wan")
    return data


def _full_link_dict(link: sqlite3.Row, mode: str) -> dict:
    data = {
        "id": link["id"],
        "group_id": link["group_id"],
        "name": link["name"],
        "url_lan": link["url_lan"],
        "url_wan": link["url_wan"],
        "url": _effective_url(link, mode),
        "icon_type": link["icon_type"],
        "icon_value": link["icon_value"],
        "description": link["description"],
        "tags": json.loads(link["tags"] or "[]"),
        "is_public": bool(link["is_public"]),
        "guest_url_mode": link["guest_url_mode"],
        "sort_order": link["sort_order"],
        "open_mode": link["open_mode"],
    }
    return data


@router.get("/api/panel")
def panel(
    request: Request,
    user: sqlite3.Row | None = Depends(optional_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    settings = request.app.state.settings
    site = get_site_settings(conn)
    public_mode = site.get("public_mode", "true") == "true" and settings.public_mode
    if user is None and not public_mode:
        raise HTTPException(status_code=401, detail="访客视图已关闭")

    site_payload = dict(site)
    site_payload["oidc_enabled"] = settings.oidc_enabled

    if user is not None:
        mode_row = conn.execute(
            "SELECT value FROM settings WHERE user_id = ? AND key = 'link_mode'",
            (user["id"],),
        ).fetchone()
        mode = mode_row["value"] if mode_row else "lan"
        groups = conn.execute(
            "SELECT * FROM groups WHERE user_id = ? ORDER BY sort_order, id",
            (user["id"],),
        ).fetchall()
        links = conn.execute(
            "SELECT * FROM links WHERE user_id = ? ORDER BY sort_order, id",
            (user["id"],),
        ).fetchall()
        group_payload = []
        for group in groups:
            group_links = [
                _full_link_dict(l, mode)
                for l in links
                if l["group_id"] == group["id"]
            ]
            group_payload.append({**dict(group), "links": group_links})
        ungrouped = [
            _full_link_dict(l, mode) for l in links if l["group_id"] is None
        ]
        return {"site": site_payload, "groups": group_payload, "ungrouped": ungrouped}

    public_group_ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM groups WHERE user_id IS NOT NULL AND is_public = 1 "
            "ORDER BY sort_order, id"
        ).fetchall()
    ]
    if public_group_ids:
        placeholders = ",".join("?" for _ in public_group_ids)
        group_rows = conn.execute(
            f"SELECT * FROM groups WHERE id IN ({placeholders}) ORDER BY sort_order, id",
            public_group_ids,
        ).fetchall()
    else:
        group_rows = []
    link_rows = conn.execute(
        "SELECT * FROM links WHERE is_public = 1 ORDER BY sort_order, id"
    ).fetchall()

    group_payload = []
    for group in group_rows:
        group_links = [
            _public_link_dict(l, l["guest_url_mode"] == "show")
            for l in link_rows
            if l["group_id"] == group["id"]
        ]
        group_payload.append(
            {
                "id": group["id"],
                "name": group["name"],
                "icon": group["icon"],
                "links": group_links,
            }
        )
    ungrouped = [
        _public_link_dict(l, l["guest_url_mode"] == "show")
        for l in link_rows
        if l["group_id"] is None
    ]
    return {"site": site_payload, "groups": group_payload, "ungrouped": ungrouped}


@router.get("/go/{link_id}")
def go_link(
    link_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> RedirectResponse:
    link = conn.execute(
        "SELECT * FROM links WHERE id = ? AND is_public = 1", (link_id,)
    ).fetchone()
    if link is None:
        raise HTTPException(status_code=404, detail="链接不存在或未公开")
    url = _effective_url(link, "wan")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=404, detail="链接地址无效")
    return RedirectResponse(url, status_code=302)
