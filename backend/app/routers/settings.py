from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.brand_defaults import get_site_settings
from app.db import get_db
from app.deps import current_user

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
    "public_mode",
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
    public_mode: bool | None = None


@router.get("/api/site-settings")
def site_settings_get(
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    return get_site_settings(conn)


@router.put("/api/site-settings")
def site_settings_put(
    body: SiteSettingsIn,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    payload = body.model_dump(exclude_unset=True)
    for key, value in payload.items():
        if key == "public_mode":
            value = "true" if value else "false"
        conn.execute(
            "INSERT INTO site_settings (key, value, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, str(value)),
        )
    return get_site_settings(conn)


class UserSettingsIn(BaseModel):
    theme: str | None = None
    link_mode: str | None = None


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
        conn.execute(
            "INSERT INTO settings (user_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
            (user["id"], key, str(value)),
        )
    return user_settings_get(user, conn)


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
