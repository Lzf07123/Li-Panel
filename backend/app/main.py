from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.brand_defaults import seed_site_defaults
from app.config import Settings, load_settings
from app.db import connect, init_schema
from app.routers import audit, auth, backup, groups, links, panel, rss, sessions, setup, sso, tags
from app.routers import health as health_router
from app.routers import settings as settings_router
from app.security import RateLimiter
from app.version import VERSION

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIST_CANDIDATES = [
    PROJECT_ROOT / "frontend" / "dist",
    Path.cwd() / "frontend" / "dist",
]
FRONTEND_DIST = next(
    (path for path in DIST_CANDIDATES if (path / "index.html").is_file()),
    PROJECT_ROOT / "frontend" / "dist",
)

def _netloc_key(parsed) -> str:
    """Origin/Host 归一化键：host:port，默认端口（80/443）等价于无端口。

    用于 CSRF Origin 校验：比较完整 host+port，堵住「同 host 不同端口」缺口，
    同时避免 HTTPS 部署下 Host 带 :443 而 Origin 不带端口的误拒。
    """
    hostname = parsed.hostname or ""
    port = parsed.port
    if port in (None, 80, 443):
        return hostname
    return f"{hostname}:{port}"


def _build_csp(settings: Settings) -> str:
    """构造 CSP：生产禁用内联样式；开发保留以支撑前端动效的内联样式（与参考实现一致）。"""
    style_src = (
        "'self'" if settings.environment == "production" else "'self' 'unsafe-inline'"
    )
    return (
        f"default-src 'self'; connect-src 'self' https: http:; "
        f"img-src 'self' data:; style-src {style_src}; font-src 'self' data:; "
        f"object-src 'none'; base-uri 'self'; form-action 'self'; "
        f"frame-src 'self' https: http:; frame-ancestors 'none'"
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    if settings.environment == "production" and len(settings.secret_key) < 32:
        raise RuntimeError("PANEL_SECRET_KEY 长度必须 ≥ 32 字符（生产环境）")
    if settings.host_cookie and not settings.cookie_secure:
        raise RuntimeError(
            "PANEL_HOST_COOKIE=true 时必须同时设置 PANEL_COOKIE_SECURE=true"
            "（__Host- 前缀 Cookie 强制要求 Secure 属性）"
        )
    app = FastAPI(
        title="Li&Panel",
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None if settings.environment == "production" else "/redoc",
        openapi_url=None if settings.environment == "production" else "/openapi.json",
    )
    csp = _build_csp(settings)
    app.state.settings = settings
    app.state.db_path = settings.db_path
    app.state.uploads_dir = settings.uploads_dir
    from app.security import LoginLockout

    app.state.login_lockout = LoginLockout(
        max_fails=settings.login_max_fails, lock_minutes=settings.login_lock_minutes
    )
    app.state.login_limiter = RateLimiter(limit=10, window_seconds=60)
    app.state.setup_limiter = RateLimiter(limit=10, window_seconds=60)
    app.state.sso_limiter = RateLimiter(limit=10, window_seconds=60)

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    try:
        conn = connect(settings.db_path)
    except sqlite3.OperationalError as exc:
        raise RuntimeError(
            "无法打开数据库文件，数据目录不可写或权限不足。"
            f"（{settings.db_path}）请先执行：bash scripts/fix-data-owner.sh "
            "或 sudo chown -R 10001:10001 ./data"
        ) from exc
    init_schema(conn)
    seed_site_defaults(conn, settings.public_mode)
    conn.close()

    def _host_allowed(host: str) -> bool:
        if not settings.allowed_hosts:
            return True
        # "//" 前缀使 urlparse 支持无 scheme 的 Host 头，并正确解析 IPv6 字面量 [::1]:port
        parsed = urlparse("//" + host)
        hostname = parsed.hostname or ""
        for allowed in settings.allowed_hosts:
            if allowed == hostname:
                return True
            if allowed.startswith("*.") and hostname.endswith(allowed[1:]):
                return True
        return False

    @app.middleware("http")
    async def security(request: Request, call_next):
        if not _host_allowed(request.headers.get("host", "")):
            return JSONResponse({"error": "Host 不在白名单"}, status_code=403)
        if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
            origin = request.headers.get("origin")
            if origin:
                parsed_origin = urlparse(origin)
                if parsed_origin.scheme not in {"http", "https"} or not parsed_origin.hostname:
                    return JSONResponse(
                        {"error": "跨域请求被拒绝"}, status_code=403
                    )
                # 代理（nginx）透传了原始 Host（含端口）时，用完整 netloc 严格校验，
                # 堵住「同 host 不同端口」缺口。
                forwarded = request.headers.get("x-forwarded-host")
                if forwarded:
                    parsed_host = urlparse("//" + forwarded)
                    if (
                        not parsed_host.hostname
                        or _netloc_key(parsed_origin) != _netloc_key(parsed_host)
                    ):
                        return JSONResponse(
                            {"error": "跨域请求被拒绝"}, status_code=403
                        )
                else:
                    # 未透传端口（nginx 默认 $host 剥离端口）：回退 hostname 比较，
                    # 避免 IP:端口 + 反代部署下所有写请求被误拒（SameSite=Lax 兜底）。
                    parsed_host = urlparse("//" + (request.headers.get("host") or ""))
                    if not parsed_host.hostname or parsed_host.hostname != parsed_origin.hostname:
                        return JSONResponse(
                            {"error": "跨域请求被拒绝"}, status_code=403
                        )
        response = await call_next(request)
        response.headers["content-security-policy"] = csp
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["referrer-policy"] = "no-referrer"
        response.headers["cross-origin-opener-policy"] = "same-origin"
        response.headers["cross-origin-resource-policy"] = "same-origin"
        response.headers["permissions-policy"] = (
            "camera=(), microphone=(), geolocation=(), usb=()"
        )
        if settings.hsts:
            response.headers["strict-transport-security"] = (
                "max-age=63072000; includeSubDomains"
            )
        if request.url.path.startswith(("/api/", "/auth/")):
            response.headers["cache-control"] = "no-store"
        elif request.url.path.startswith("/assets/"):
            response.headers["cache-control"] = (
                "public, max-age=31536000, immutable"
            )
        elif "text/html" in response.headers.get("content-type", ""):
            # SPA 入口：不缓存，保证发版后立即拿到新 index（资源本身已 immutable）
            response.headers["cache-control"] = "no-cache"
        response.headers["x-panel-version"] = VERSION
        return response

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "version": VERSION}

    app.include_router(setup.router)
    app.include_router(auth.router)
    app.include_router(sso.router)
    app.include_router(groups.router)
    app.include_router(links.router)
    app.include_router(panel.router)
    app.include_router(settings_router.router)
    app.include_router(tags.router)
    app.include_router(backup.router)
    app.include_router(rss.router)
    app.include_router(sessions.router)
    app.include_router(audit.router)
    app.include_router(health_router.router)

    if (FRONTEND_DIST / "assets").exists():
        app.mount(
            "/assets",
            StaticFiles(directory=FRONTEND_DIST / "assets"),
            name="assets",
        )

    @app.get("/{path:path}", include_in_schema=False)
    def spa_fallback(path: str) -> FileResponse:
        if path.startswith(("api/", "auth/", "go/", "uploads/", "favicons/")):
            raise HTTPException(status_code=404)
        # 防路径穿越：拒绝反斜杠与任何 ".." 段（浏览器会把 \ 规范化为 /）
        if "\\" in path or any(part == ".." for part in path.split("/")):
            raise HTTPException(status_code=404)
        candidate = (FRONTEND_DIST / path).resolve()
        if not candidate.is_relative_to(FRONTEND_DIST.resolve()):
            raise HTTPException(status_code=404)
        if candidate.is_file():
            return FileResponse(candidate)
        index = FRONTEND_DIST / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="前端尚未构建")

    return app


app = create_app()
