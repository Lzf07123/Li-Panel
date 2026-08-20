from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Depends

from app.db import get_db
from app.deps import current_user
from app.rss import MAX_FEEDS, fetch_feed

router = APIRouter(prefix="/api/rss", tags=["rss"])


@router.get("")
def rss_feeds(
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """当前用户的订阅源解析结果（每源 ≤10 条，失败返回空 items）。"""
    row = conn.execute(
        "SELECT value FROM settings WHERE user_id = ? AND key = 'rss_feeds'",
        (user["id"],),
    ).fetchone()
    urls: list[str] = []
    if row is not None:
        try:
            parsed = json.loads(row["value"])
            if isinstance(parsed, list):
                urls = [u for u in parsed if isinstance(u, str)][:MAX_FEEDS]
        except json.JSONDecodeError:
            urls = []
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_FEEDS) as pool:
        futures = {pool.submit(fetch_feed, url): url for url in urls}
        for future in as_completed(futures):
            url = futures[future]
            items = future.result() or []
            results.append({"feed_url": url, "items": items})
    return {"feeds": results}
