"""站点 favicon 抓取：受控出站请求（开关、超时、并发上限、内存缓存、大小与类型白名单）。

识别增强（2026-08-21）：
- 解析全部 <link> 候选（icon / shortcut icon / apple-touch-icon / 其它含 icon 的 rel）
- 按 sizes 择优（越大越清晰，上限 512），同分优先 apple-touch-icon
- 支持 <base href> 解析相对地址、data: URI 内联图标
- 无 link 时回退源站 /favicon.ico
- 支持 png / jpeg / webp / ico / svg，按真实 Content-Type 保存正确扩展名
"""
from __future__ import annotations

import base64
import re
import threading
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

ICON_CONTENT_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/x-icon": "ico",
    "image/vnd.microsoft.icon": "ico",
    "image/svg+xml": "svg",
}
DATA_URI_RE = re.compile(
    r"^data:image/(png|jpeg|webp|svg\+xml|x-icon|vnd\.microsoft\.icon);base64,(.+)$",
    re.IGNORECASE,
)
MAX_ICON_BYTES = 1_048_576  # 1MB
FETCH_TIMEOUT = 5.0
CACHE_TTL = 60.0
MAX_CONCURRENCY = 4
MAX_PREFERRED_SIZE = 512

_semaphore = threading.BoundedSemaphore(MAX_CONCURRENCY)
_cache: dict[int, tuple[float, str | None]] = {}
_cache_lock = threading.Lock()


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.base_href: str | None = None
        self.candidates: list[dict] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        if tag == "base" and attributes.get("href"):
            self.base_href = attributes["href"]
        if tag != "link" or not attributes.get("href"):
            return
        rel = (attributes.get("rel") or "").lower()
        if "icon" not in rel:
            return
        sizes = attributes.get("sizes", "")
        size = 0
        if re.fullmatch(r"\d+x\d+", sizes):
            size = int(sizes.split("x")[0])
        self.candidates.append(
            {
                "href": attributes["href"],
                "rel": rel,
                "size": size,
                "apple": "apple-touch-icon" in rel,
            }
        )


def _allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _ext_for(content_type: str) -> str | None:
    ctype = content_type.split(";")[0].strip().lower()
    return ICON_CONTENT_TYPES.get(ctype)


def _ext_for_data_uri(mime: str) -> str | None:
    return ICON_CONTENT_TYPES.get(f"image/{mime}")


def _decode_data_uri(href: str) -> tuple[bytes, str] | None:
    match = DATA_URI_RE.match(href)
    if match is None:
        return None
    mime, payload = match.group(1), match.group(2)
    ext = _ext_for_data_uri(mime)
    if ext is None:
        return None
    try:
        data = base64.b64decode(payload + "=" * (-len(payload) % 4))
    except (ValueError, base64.binascii.Error):
        return None
    if not data or len(data) > MAX_ICON_BYTES:
        return None
    return data, ext


def _pick_icon_url(html: str, page_url: str) -> str | None:
    """从 HTML 提取最优图标地址；无则回退源站 /favicon.ico。"""
    collector = _LinkCollector()
    try:
        collector.feed(html)
    except Exception:
        return None
    if collector.candidates:
        base = collector.base_href or page_url
        best = max(
            collector.candidates,
            key=lambda c: (
                c["apple"],
                min(c["size"], MAX_PREFERRED_SIZE) if c["size"] else 0,
            ),
        )
        return urljoin(base, best["href"])
    parsed = urlparse(page_url)
    return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"


def _download(url: str, timeout: float = FETCH_TIMEOUT) -> tuple[bytes, str | None]:
    """GET 并返回 (bytes, ext)；失败或类型不合规返回 (None, None)。"""
    if url.startswith("data:image/"):
        return _decode_data_uri(url) or (None, None)
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
    # 非图片响应（通常是 HTML）：解析 icon 候选
    html = data.decode("utf-8", errors="ignore")
    icon_url = _pick_icon_url(html, url)
    if icon_url == url:
        return None, None
    return _download(icon_url, timeout)


def fetch_favicon(
    url: str,
    timeout: float = FETCH_TIMEOUT,
) -> tuple[bytes, str] | None:
    """抓取 favicon，返回 (bytes, ext)；失败返回 None。并发受限。"""
    with _semaphore:
        result = _download(url, timeout)
        if result is None or result[0] is None:
            return None
        return result


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
