from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from app.db import get_db
from app.deps import current_user
from app.health import check_url, get_cached, set_cached

router = APIRouter(prefix="/api/health", tags=["health"])

MAX_WORKERS = 4


def _effective_url(link: sqlite3.Row) -> str:
    return link["url_wan"] or link["url_lan"]


@router.get("/links")
def health_links(
    request: Request,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """当前用户全部链接的健康状态（up/down/unknown + 响应毫秒），并发 ≤4。"""
    settings = request.app.state.settings
    if not settings.health_check:
        return {"enabled": False, "results": []}
    links = conn.execute(
        "SELECT id, url_lan, url_wan FROM links WHERE user_id = ?", (user["id"],)
    ).fetchall()

    results: list[dict] = []
    pending: dict = {}
    for link in links:
        cached = get_cached(link["id"])
        if cached is not None:
            status, ms = cached
            results.append(
                {
                    "link_id": link["id"],
                    "status": status,
                    "ms": ms,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        else:
            pending[link["id"]] = link

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(check_url, _effective_url(link)): link_id
            for link_id, link in pending.items()
        }
        for future in as_completed(futures):
            link_id = futures[future]
            status, ms = future.result()
            set_cached(link_id, status, ms)
            results.append(
                {
                    "link_id": link_id,
                    "status": status,
                    "ms": ms,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
            )
    results.sort(key=lambda item: item["link_id"])
    return {"enabled": True, "results": results}
