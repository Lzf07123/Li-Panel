"""RSS/ATOM 订阅抓取：受控出站（≤3 源、8s 超时、并发 ≤3、10min 缓存）。

使用标准库 xml.etree 解析，不引入外部依赖；解析失败返回 None。
"""
from __future__ import annotations

import threading
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import httpx

MAX_FEEDS = 3
FETCH_TIMEOUT = 8.0
CACHE_TTL = 600.0
MAX_CONCURRENCY = 3
MAX_ITEMS_PER_FEED = 10

_semaphore = threading.BoundedSemaphore(MAX_CONCURRENCY)
_cache: dict[str, tuple[float, list[dict] | None]] = {}
_cache_lock = threading.Lock()


def allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _text(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None else ""


def _parse_rss(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    items: list[dict] = []
    for item in root.findall(".//item"):
        title = _text(item.find("title"))
        link = _text(item.find("link"))
        if not title or not allowed_url(link):
            continue
        items.append(
            {
                "title": title,
                "link": link,
                "pub_date": _text(item.find("pubDate")),
                "description": _text(item.find("description"))[:300],
            }
        )
    return items


def _parse_atom(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items: list[dict] = []
    for entry in root.findall("atom:entry", ns):
        title = _text(entry.find("atom:title", ns))
        link_el = entry.find("atom:link", ns)
        link = ""
        if link_el is not None:
            link = link_el.attrib.get("href", "")
        if not title or not allowed_url(link):
            continue
        items.append(
            {
                "title": title,
                "link": link,
                "pub_date": _text(entry.find("atom:updated", ns)),
                "description": _text(entry.find("atom:summary", ns))[:300],
            }
        )
    return items


def _parse(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    if root.tag == "rss":
        return _parse_rss(xml_text)
    if root.tag == "feed":
        return _parse_atom(xml_text)
    return []


def _fetch_once(url: str) -> list[dict] | None:
    try:
        resp = httpx.get(
            url,
            timeout=FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "LiPanel/1.0"},
        )
        resp.raise_for_status()
        return _parse(resp.text)
    except (httpx.HTTPError, ET.ParseError, ValueError):
        return None


def fetch_feed(url: str) -> list[dict] | None:
    """带缓存与并发的订阅抓取；失败返回 None（调用方按空处理）。"""
    with _cache_lock:
        cached = _cache.get(url)
        if cached is not None and time.monotonic() - cached[0] < CACHE_TTL:
            return cached[1]
    with _semaphore:
        result = _fetch_once(url)
        with _cache_lock:
            _cache[url] = (time.monotonic(), result)
        return result
