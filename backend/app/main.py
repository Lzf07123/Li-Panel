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
from app.routers import auth, backup, groups, links, panel, rss, setup, sso, tags
from app.routers import health as health_router
from app.routers import settings as settings_router
from app.security import RateLimiter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIST_CANDIDATES = [
    PROJECT_ROOT / "frontend" / "dist",
    Path.cwd() / "frontend" / "dist",
]
FRONTEND_DIST = next(
    (path for path in DIST_CANDIDATES if (path / "index.html").is_file()),
    PROJECT_ROOT / "frontend" / "dist",
)

def _build_csp(settings: Settings) -> str:
    """构造 CSP：生产禁用内联样式；开发保留以支撑前端动效的内联样式（与参考实现一致）。"""
    style_src = (
        "'self'" if settings.environment == "production" else "'self' 'unsafe-inline'"
    )
    return (
        f"default-src 'self'; connect-src 'self'; "
        f"img-src 'self' data:; style-src {style_src}; object-src 'none'; "
        f"base-uri 'self'; form-action 'self'; frame-src 'self' https: http:; "
        f"frame-ancestors 'none'"
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
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
    conn = connect(settings.db_path)
    init_schema(conn)
    seed_site_defaults(conn, settings.public_mode)
    conn.close()

    def _host_allowed(host: str) -> bool:
        if not settings.allowed_hosts:
            return True
        hostname = host.split(":")[0]
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
                origin_host = urlparse(origin).hostname
                host = request.headers.get("host", "").split(":")[0]
                if origin_host != host:
                    return JSONResponse(
                        {"error": "跨域请求被拒绝"}, status_code=403
                    )
        response = await call_next(request)
        response.headers["content-security-policy"] = csp
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["referrer-policy"] = "no-referrer"
        if request.url.path.startswith(("/api/", "/auth/")):
            response.headers["cache-control"] = "no-store"
        return response

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

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
        candidate = FRONTEND_DIST / path
        if candidate.is_file():
            return FileResponse(candidate)
        index = FRONTEND_DIST / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="前端尚未构建")

    return app


app = create_app()
