"""站点 favicon 抓取：受控出站请求（开关、超时、并发上限、内存缓存、大小与类型白名单）。

识别增强（2026-08-21 第二轮）：
1. <link> 图标候选：icon / shortcut icon / apple-touch-icon / mask-icon 等含 icon 的 rel，
   按 sizes 择优（上限 512，尺寸优先、apple-touch 次之）
2. <link rel="manifest">：解析 Web App Manifest icons[]（purpose any/maskable，sizes 择优）
3. <meta> 图标：msapplication-TileImage、og:image、twitter:image / twitter:image:src
4. 根目录回退：/favicon.ico → /favicon.png → /favicon.svg
5. data: URI：base64（png/jpeg/webp/svg/x-icon）与非 base64 内联 SVG
6. <base href> 相对地址解析；按真实 Content-Type 保存正确扩展名（png/jpg/webp/ico/svg）
"""
from __future__ import annotations

import base64
import re
import threading
import time
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse

import httpx

ICON_CONTENT_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/x-icon": "ico",
    "image/vnd.microsoft.icon": "ico",
    "image/svg+xml": "svg",
}
DATA_URI_B64_RE = re.compile(
    r"^data:image/(png|jpeg|webp|svg\+xml|x-icon|vnd\.microsoft\.icon);base64,(.+)$",
    re.IGNORECASE,
)
MAX_ICON_BYTES = 1_048_576  # 1MB
MAX_MANIFEST_BYTES = 524_288  # 512KB
FETCH_TIMEOUT = 5.0
CACHE_TTL = 60.0
MAX_CONCURRENCY = 4
MAX_PREFERRED_SIZE = 512
MAX_DEPTH = 3

_semaphore = threading.BoundedSemaphore(MAX_CONCURRENCY)
_cache: dict[int, tuple[float, str | None]] = {}
_cache_lock = threading.Lock()

_META_IMAGE_NAMES = {
    "msapplication-tileimage",
    "og:image",
    "twitter:image",
    "twitter:image:src",
}


class _HtmlCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.base_href: str | None = None
        self.manifest: str | None = None
        self.icons: list[dict] = []
        self.meta_images: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        if tag == "base" and attributes.get("href"):
            self.base_href = attributes["href"]
        if tag == "link":
            href = attributes.get("href")
            rel = (attributes.get("rel") or "").lower()
            if href and rel == "manifest":
                self.manifest = href
            if href and rel == "image_src":
                self.meta_images.append(href)
            if href and "icon" in rel:
                sizes = attributes.get("sizes", "")
                size = 0
                if re.fullmatch(r"\d+x\d+", sizes):
                    size = int(sizes.split("x")[0])
                self.icons.append(
                    {
                        "href": href,
                        "size": size,
                        "apple": "apple-touch-icon" in rel,
                    }
                )
        if tag == "meta":
            name = (attributes.get("name") or attributes.get("property") or "").lower()
            content = attributes.get("content", "")
            if content and name in _META_IMAGE_NAMES:
                self.meta_images.append(content)


def _allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _ext_for(content_type: str) -> str | None:
    ctype = content_type.split(";")[0].strip().lower()
    return ICON_CONTENT_TYPES.get(ctype)


def _ext_for_data_uri(mime: str) -> str | None:
    return ICON_CONTENT_TYPES.get(f"image/{mime}")


def _decode_data_uri(href: str) -> tuple[bytes, str] | None:
    match = DATA_URI_B64_RE.match(href)
    if match is not None:
        mime, payload = match.group(1), match.group(2)
        ext = _ext_for_data_uri(mime)
        try:
            data = base64.b64decode(payload + "=" * (-len(payload) % 4))
        except (ValueError, base64.binascii.Error):
            return None
        if ext is None or not data or len(data) > MAX_ICON_BYTES:
            return None
        return data, ext
    # 非 base64 内联 SVG：data:image/svg+xml,<svg...>
    if href.startswith("data:image/svg+xml,"):
        payload = href.split(",", 1)[1]
        data = unquote(payload).encode("utf-8")
        if not data or len(data) > MAX_ICON_BYTES:
            return None
        return data, "svg"
    return None


def _pick_link_icon_url(html: str, page_url: str) -> str | None:
    """从 <link> 候选选最优图标地址（sizes 优先、apple-touch 次之）。"""
    collector = _HtmlCollector()
    try:
        collector.feed(html)
    except Exception:
        return None
    if not collector.icons:
        return None
    base = collector.base_href or page_url
    best = max(
        collector.icons,
        key=lambda c: (
            min(c["size"], MAX_PREFERRED_SIZE) if c["size"] else 0,
            c["apple"],
        ),
    )
    return urljoin(base, best["href"])


def _best_manifest_icon(
    manifest_url: str, timeout: float = FETCH_TIMEOUT
) -> str | None:
    """抓取 Web App Manifest 并择优返回图标地址（绝对地址或 data: URI）。"""
    if not _allowed_url(manifest_url):
        return None
    try:
        resp = httpx.get(
            manifest_url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "LiPanel/1.0"},
        )
        resp.raise_for_status()
        if len(resp.content) > MAX_MANIFEST_BYTES:
            return None
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    icons = data.get("icons")
    if not isinstance(icons, list):
        return None
    candidates = [
        icon for icon in icons
        if isinstance(icon, dict) and isinstance(icon.get("src"), str)
    ]
    if not candidates:
        return None

    def size_of(icon: dict) -> int:
        sizes = icon.get("sizes")
        if isinstance(sizes, str) and re.fullmatch(r"\d+x\d+", sizes.strip()):
            return min(int(sizes.split("x")[0]), MAX_PREFERRED_SIZE)
        return 0

    def purpose_score(icon: dict) -> int:
        purpose = str(icon.get("purpose") or "any").lower()
        return 0 if "any" in purpose else 1  # any 优先于仅 maskable

    best = max(candidates, key=lambda icon: (size_of(icon), -purpose_score(icon)))
    src = best["src"]
    if src.startswith("data:image/"):
        return src
    return urljoin(manifest_url, src)


def _candidate_urls(html: str, page_url: str) -> list[str]:
    """按优先级返回候选图标地址（link 图标 → manifest → meta → 根目录回退）。"""
    collector = _HtmlCollector()
    try:
        collector.feed(html)
    except Exception:
        return []
    base = collector.base_href or page_url
    urls: list[str] = []
    if collector.icons:
        best = max(
            collector.icons,
            key=lambda c: (
                min(c["size"], MAX_PREFERRED_SIZE) if c["size"] else 0,
                c["apple"],
            ),
        )
        urls.append(urljoin(base, best["href"]))
    if collector.manifest:
        urls.append(f"manifest:{urljoin(base, collector.manifest)}")
    for image in collector.meta_images:
        if image.startswith("data:image/") or _allowed_url(image):
            urls.append(image)
        elif image.startswith("/"):
            urls.append(urljoin(page_url, image))
        else:
            urls.append(urljoin(base, image))
    parsed = urlparse(page_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    for path in ("/favicon.ico", "/favicon.png", "/favicon.svg"):
        urls.append(origin + path)
    return urls


def _download(
    url: str,
    timeout: float = FETCH_TIMEOUT,
    depth: int = 0,
) -> tuple[bytes, str | None]:
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
    if depth >= MAX_DEPTH:
        return None, None
    # 非图片响应（通常是 HTML）：按优先级尝试候选
    html = data.decode("utf-8", errors="ignore")
    for candidate in _candidate_urls(html, url):
        if candidate == url:
            continue
        if candidate.startswith("manifest:"):
            icon_url = _best_manifest_icon(candidate[9:], timeout)
            if icon_url is None or icon_url == url:
                continue
            result = _download(icon_url, timeout, depth + 1)
        else:
            result = _download(candidate, timeout, depth + 1)
        if result is not None and result[0] is not None:
            return result
    return None, None


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
