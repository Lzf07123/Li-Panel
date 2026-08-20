from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request

from app.db import get_db
from app.deps import current_user
from app.health import check_url, get_cached, set_cached

router = APIRouter(prefix="/api/health", tags=["health"])


def _effective_url(link: sqlite3.Row) -> str:
    return link["url_wan"] or link["url_lan"]


@router.get("/links")
def health_links(
    request: Request,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """当前用户全部链接的健康状态（up/down/unknown + 响应毫秒）。"""
    settings = request.app.state.settings
    if not settings.health_check:
        return {"enabled": False, "results": []}
    links = conn.execute(
        "SELECT id, url_lan, url_wan FROM links WHERE user_id = ?", (user["id"],)
    ).fetchall()
    results = []
    for link in links:
        cached = get_cached(link["id"])
        if cached is not None:
            status, ms = cached
        else:
            status, ms = check_url(_effective_url(link))
            set_cached(link["id"], status, ms)
        results.append(
            {
                "link_id": link["id"],
                "status": status,
                "ms": ms,
                "checked_at": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
            }
        )
    return {"enabled": True, "results": results}
