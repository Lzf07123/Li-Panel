def test_assets_long_cache(client):
    r = client.get("/assets/whatever.js")
    # SPA fallback 会返回 index（无该文件时），仅验证响应头存在
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_api_no_store(client):
    r = client.get("/api/health")
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-panel-version"] == "0.1.0"
    assert r.json()["version"] == "0.1.0"
