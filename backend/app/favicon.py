"""站点 favicon 抓取：受控出站请求（开关、超时、并发上限、内存缓存、大小与类型白名单）。

设计约束（路线图 V14）：
- 只允许 http/https 且带主机名
- 超时 5s、并发 ≤4（threading.BoundedSemaphore）
- 单文件大小 ≤1MB；Content-Type 白名单（png/jpeg/webp/ico）
- 失败结果按链接 id 内存缓存 60s，避免重复抓取
"""
from __future__ import annotations

import re
import threading
import time
from urllib.parse import urljoin, urlparse

import httpx

ICON_CONTENT_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/x-icon": "ico",
    "image/vnd.microsoft.icon": "ico",
}
MAX_ICON_BYTES = 1_048_576  # 1MB
FETCH_TIMEOUT = 5.0
CACHE_TTL = 60.0
MAX_CONCURRENCY = 4

_semaphore = threading.BoundedSemaphore(MAX_CONCURRENCY)
_cache: dict[int, tuple[float, str | None]] = {}
_cache_lock = threading.Lock()

_LINK_RE = re.compile(
    r'<link[^>]+rel=["\'](?:shortcut\s+)?icon["\'][^>]*>', re.IGNORECASE
)
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)


def _allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _ext_for(content_type: str) -> str | None:
    ctype = content_type.split(";")[0].strip().lower()
    return ICON_CONTENT_TYPES.get(ctype)


def _download(url: str, timeout: float = FETCH_TIMEOUT) -> tuple[bytes, str | None]:
    """GET 并返回 (bytes, ext)；失败或类型不合规返回 (None, None)。"""
    if not _allowed_url(url):
        return None, None
    try:
        resp = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "LiPanel/1.0"},
        )
        resp.raise_for_status()
    except httpx.HTTPError:
        return None, None
    data = resp.content
    if not data or len(data) > MAX_ICON_BYTES:
        return None, None
    ext = _ext_for(resp.headers.get("content-type", ""))
    if ext is not None:
        return data, ext
    # 非图片响应（通常是 HTML）：解析 <link rel=icon>
    html = data.decode("utf-8", errors="ignore")
    match = _LINK_RE.search(html)
    if match is None:
        return None, None
    href_match = _HREF_RE.search(match.group(0))
    if href_match is None:
        return None, None
    icon_url = urljoin(url, href_match.group(1))
    if icon_url == url:
        return None, None
    return _download(icon_url, timeout)


def fetch_favicon(
    url: str,
    timeout: float = FETCH_TIMEOUT,
) -> bytes | None:
    """抓取 favicon 字节；失败返回 None。并发受限。"""
    with _semaphore:
        data, _ = _download(url, timeout)
        return data


def get_cached(link_id: int) -> str | None:
    """返回缓存的可展示路径或 None（含失败缓存）。"""
    with _cache_lock:
        entry = _cache.get(link_id)
        if entry is None:
            return None
        cached_at, path = entry
        if time.monotonic() - cached_at > CACHE_TTL:
            _cache.pop(link_id, None)
            return None
        return path


def set_cached(link_id: int, path: str | None) -> None:
    with _cache_lock:
        _cache[link_id] = (time.monotonic(), path)
