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
    "image/gif": "gif",
    "image/webp": "webp",
    "image/x-icon": "ico",
    "image/vnd.microsoft.icon": "ico",
    "image/svg+xml": "svg",
}
DATA_URI_B64_RE = re.compile(
    r"^data:image/(png|jpeg|webp|svg\+xml|x-icon|vnd\.microsoft\.icon);base64,(.+)$",
    re.IGNORECASE,
)
MAX_ICON_BYTES = 1_048_576  # 1MB（图标本体上限）
MAX_PAGE_BYTES = 5 * 1_048_576  # 5MB（首页 HTML 解析候选上限，Cloudflare 首页约 1.3MB）
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


def _sniff_ext(data: bytes) -> str | None:
    """按魔数识别图片格式（不依赖 Content-Type）。

    覆盖三类真实场景：
    - Docker Hub：favicon.ico 以 application/octet-stream 返回（实际为 PNG）
    - Cloudflare：favicon.ico 声明 image/x-icon 但内容实为 PNG
    - 文本 SVG：无二进制魔数，按 <svg/<?xml 前缀识别
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    if data.startswith(b"\x00\x00\x01\x00"):
        return "ico"
    head = data[:512].lstrip().lower()
    if head.startswith((b"<svg", b"<?xml")):
        return "svg"
    return None


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
    if not data:
        return None, None
    ctype = resp.headers.get("content-type", "")
    ext = _ext_for(ctype)
    sniffed = _sniff_ext(data)
    if sniffed is not None:
        # 魔数为准：修复 octet-stream（Docker Hub）与「声明 ico 实为 PNG」（Cloudflare）等类型错乱
        if len(data) <= MAX_ICON_BYTES:
            return data, sniffed
        return None, None
    if ext == "svg":
        # 文本 SVG 无魔数，按 Content-Type 接受
        if len(data) <= MAX_ICON_BYTES:
            return data, "svg"
        return None, None
    if ext is not None:
        # 声明为图片但魔数未知：若实际是 HTML 错误页则走候选，否则按声明类型接受
        head = data[:512].lstrip().lower()
        if not head.startswith((b"<html", b"<!doctype")):
            if len(data) <= MAX_ICON_BYTES:
                return data, ext
            return None, None
    # 非图片响应（HTML/壳页）：解析候选；页面大小上限独立于图标本体（Cloudflare 首页约 1.3MB）
    if len(data) > MAX_PAGE_BYTES or depth >= MAX_DEPTH:
        return None, None
    html = data.decode("utf-8", errors="ignore")
    seen: set[str] = set()
    for candidate in _candidate_urls(html, url):
        if candidate == url or candidate in seen:
            continue
        seen.add(candidate)
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


def _parent_domain_favicon(url: str) -> str | None:
    """子域名失败兜底：尝试父域名的根 favicon（如 dash.cloudflare.com → cloudflare.com/favicon.ico）。

    仅用于「自身域名完全抓不到」时的最后手段；www. 与根域等价，不改变结果。
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    labels = parsed.hostname.lower().split(".")
    if len(labels) <= 2:
        return None  # 本身已是注册域（含 www. 二级结构由后续 join 处理）
    candidate = ".".join(labels[1:])
    if not candidate:
        return None
    return f"{parsed.scheme}://{candidate}/favicon.ico"


def fetch_favicon(
    url: str,
    timeout: float = FETCH_TIMEOUT,
) -> tuple[bytes, str] | None:
    """抓取 favicon，返回 (bytes, ext)；失败返回 None。并发受限。

    自身域名全部候选失败后，兜底尝试父域名根 /favicon.ico（dash.cloudflare.com 等
    受 JS 挑战保护的子站可借此拿到同品牌图标）。
    """
    with _semaphore:
        result = _download(url, timeout)
        if result is not None and result[0] is not None:
            return result
        parent = _parent_domain_favicon(url)
        if parent is not None:
            result = _download(parent, timeout)
            if result is not None and result[0] is not None:
                return result
        return None


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
