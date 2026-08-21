def test_assets_long_cache(client):
    r = client.get("/assets/whatever.js")
    # SPA fallback 会返回 index（无该文件时），仅验证响应头存在
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_api_no_store(client):
    r = client.get("/api/health")
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-panel-version"] == "0.1.0"
    assert r.json()["version"] == "0.1.0"


def test_index_html_no_cache(client):
    """上线前修复：SPA 入口 index.html 不缓存，发版后立即生效。"""
    r = client.get("/")
    assert "text/html" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-cache"
