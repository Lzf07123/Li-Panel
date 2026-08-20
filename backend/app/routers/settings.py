from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.brand_defaults import get_site_settings
from app.db import get_db
from app.audit import write_audit
from app.deps import current_user, optional_user
from app.rss import MAX_FEEDS, allowed_url

router = APIRouter(tags=["settings"])

ALLOWED_UPLOAD_EXTS = {"webp", "png", "jpg", "jpeg", "gif"}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024

SITE_KEYS = {
    "site_name",
    "slogan",
    "description",
    "logo",
    "favicon",
    "footer_text",
    "icp",
    "icp_url",
    "icp_icon",
    "police_text",
    "police_url",
    "police_icon",
    "public_mode",
    "notify_url",
    "notify_enabled",
}

USER_KEYS = {"theme", "link_mode"}
THEME_VALUES = {"light", "dark", "system"}
LINK_MODE_VALUES = {"lan", "wan"}


class SiteSettingsIn(BaseModel):
    site_name: str | None = Field(default=None, max_length=100)
    slogan: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    logo: str | None = Field(default=None, max_length=500)
    favicon: str | None = Field(default=None, max_length=500)
    footer_text: str | None = Field(default=None, max_length=200)
    icp: str | None = Field(default=None, max_length=100)
    icp_url: str | None = Field(default=None, max_length=500)
    icp_icon: str | None = Field(default=None, max_length=500)
    police_text: str | None = Field(default=None, max_length=100)
    police_url: str | None = Field(default=None, max_length=500)
    police_icon: str | None = Field(default=None, max_length=500)
    public_mode: bool | None = None
    notify_url: str | None = Field(default=None, max_length=500)
    notify_enabled: bool | None = None


@router.get("/api/site-settings")
def site_settings_get(
    user: sqlite3.Row | None = Depends(optional_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    data = get_site_settings(conn)
    # notify_url 是通知 webhook 地址，视为敏感配置：仅管理员可见
    if user is None or user["role"] != "admin":
        data.pop("notify_url", None)
        data.pop("notify_enabled", None)
    return data


@router.put("/api/site-settings")
def site_settings_put(
    body: SiteSettingsIn,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可修改站点信息")
    payload = body.model_dump(exclude_unset=True)
    write_audit(conn, user["id"], "site_settings_update", ",".join(payload.keys()))
    for key, value in payload.items():
        if key == "public_mode":
            value = "true" if value else "false"
        if key == "notify_enabled":
            value = "true" if value else "false"
        if key == "notify_url" and value and not value.startswith(("http://", "https://")):
            raise HTTPException(status_code=422, detail="通知地址必须以 http(s):// 开头")
        conn.execute(
            "INSERT INTO site_settings (key, value, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, str(value)),
        )
    return get_site_settings(conn)


class UserSettingsIn(BaseModel):
    theme: str | None = None
    link_mode: str | None = None
    lang: str | None = None
    rss_feeds: list[str] | None = None


@router.get("/api/settings")
def user_settings_get(
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    rows = conn.execute(
        "SELECT key, value FROM settings WHERE user_id = ?", (user["id"],)
    ).fetchall()
    return {row["key"]: row["value"] for row in rows}


@router.put("/api/settings")
def user_settings_put(
    body: UserSettingsIn,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    payload = body.model_dump(exclude_unset=True)
    for key, value in payload.items():
        if key == "theme" and value not in THEME_VALUES:
            raise HTTPException(status_code=422, detail="theme 取值非法")
        if key == "link_mode" and value not in LINK_MODE_VALUES:
            raise HTTPException(status_code=422, detail="link_mode 取值非法")
        if key == "lang" and value not in {"zh-CN", "en-US"}:
            raise HTTPException(status_code=422, detail="lang 取值非法")
        if key == "rss_feeds":
            if not isinstance(value, list):
                raise HTTPException(status_code=422, detail="rss_feeds 必须是数组")
            if len(value) > MAX_FEEDS:
                raise HTTPException(status_code=422, detail=f"最多 {MAX_FEEDS} 个订阅源")
            for feed in value:
                if not isinstance(feed, str) or not allowed_url(feed):
                    raise HTTPException(
                        status_code=400, detail=f"订阅源地址不合法：{feed!r}"
                    )
            value = json.dumps(value, ensure_ascii=False)
        conn.execute(
            "INSERT INTO settings (user_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
            (user["id"], key, str(value)),
        )
    return user_settings_get(user, conn)


MAGIC_BYTES = {
    "png": b"\x89PNG\r\n\x1a\n",
    "jpg": b"\xff\xd8\xff",
    "jpeg": b"\xff\xd8\xff",
    "gif": b"GIF8",
}


def _magic_ok(ext: str, data: bytes) -> bool:
    signature = MAGIC_BYTES.get(ext)
    if signature is None:  # webp：RIFF....WEBP
        return data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    return data.startswith(signature)


@router.post("/api/uploads")
def upload_file(
    request: Request,
    file: UploadFile,
    user: sqlite3.Row = Depends(current_user),
) -> dict:
    ext = Path(file.filename or "").suffix.lower().lstrip(".")
    if ext not in ALLOWED_UPLOAD_EXTS:
        raise HTTPException(status_code=422, detail="仅支持 webp/png/jpg/jpeg/gif")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=422, detail="仅支持图片文件")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=422, detail="图片不能超过 2MB")
    if not _magic_ok(ext, data):
        raise HTTPException(status_code=422, detail="文件内容与扩展名不符")
    name = f"{uuid4().hex}.{ext}"
    uploads_dir = request.app.state.settings.uploads_dir
    uploads_dir.mkdir(parents=True, exist_ok=True)
    (uploads_dir / name).write_bytes(data)
    return {"url": f"/uploads/{name}"}


@router.get("/favicons/{name}")
def favicon_file(request: Request, name: str) -> FileResponse:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        raise HTTPException(status_code=404, detail="文件不存在")
    path = request.app.state.settings.data_dir / "favicons" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path)


@router.get("/uploads/{name}")
def uploaded_file(request: Request, name: str) -> FileResponse:
    if "." not in name or name.rsplit(".", 1)[1].lower() not in ALLOWED_UPLOAD_EXTS:
        raise HTTPException(status_code=404, detail="文件不存在")
    path = request.app.state.settings.uploads_dir / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path)
