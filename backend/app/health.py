"""链接健康检查：受控出站（开关、超时 5s、并发 ≤4、60s 内存缓存）。

- HEAD 优先，405/501 回退 GET（流式读完即弃）
- 任何 HTTP 响应（<500）视为 up；≥500 或网络/超时视为 down
- 缓存按 link_id 60s，避免面板轮询重复出站
"""
from __future__ import annotations

import threading
import time

import httpx

CHECK_TIMEOUT = 5.0
CACHE_TTL = 60.0
MAX_CONCURRENCY = 4

_semaphore = threading.BoundedSemaphore(MAX_CONCURRENCY)
_cache: dict[int, tuple[float, str, int]] = {}
_cache_lock = threading.Lock()


def _check_once(url: str, timeout: float = CHECK_TIMEOUT) -> tuple[str, int]:
    start = time.monotonic()
    try:
        with httpx.Client(
            timeout=timeout, follow_redirects=True,
            headers={"User-Agent": "LiPanel/1.0"},
        ) as client:
            try:
                resp = client.head(url)
            except httpx.HTTPError:
                with client.stream("GET", url) as resp:
                    status = resp.status_code
            else:
                status = resp.status_code
                if status in {405, 501}:
                    with client.stream("GET", url) as resp:
                        status = resp.status_code
    except httpx.HTTPError:
        return "down", 0
    ms = int((time.monotonic() - start) * 1000)
    return ("up" if status < 500 else "down", ms)


def check_url(url: str, timeout: float = CHECK_TIMEOUT) -> tuple[str, int]:
    """并发受限的 URL 健康检查，返回 (status, ms)。"""
    with _semaphore:
        return _check_once(url, timeout)


def get_cached(link_id: int) -> tuple[str, int] | None:
    with _cache_lock:
        entry = _cache.get(link_id)
        if entry is None:
            return None
        cached_at, status, ms = entry
        if time.monotonic() - cached_at > CACHE_TTL:
            _cache.pop(link_id, None)
            return None
        return status, ms


def set_cached(link_id: int, status: str, ms: int) -> None:
    with _cache_lock:
        _cache[link_id] = (time.monotonic(), status, ms)
