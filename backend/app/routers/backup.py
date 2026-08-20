from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.db import get_db
from app.deps import current_user

router = APIRouter(prefix="/api/backup", tags=["backup"])

BACKUP_VERSION = 1
SNAPSHOT_NAME_RE = re.compile(r"^snapshot-[A-Za-z0-9._-]+\.json$")

LINK_FIELDS = [
    "name", "url_lan", "url_wan", "icon_type", "icon_value",
    "description", "tags", "is_public", "guest_url_mode", "open_mode",
]


def _is_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _validate_backup(data: object) -> dict:
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="备份文件格式错误：顶层必须是对象")
    for key in ("groups", "links"):
        value = data.get(key)
        if not isinstance(value, list):
            raise HTTPException(
                status_code=400, detail=f"备份文件格式错误：{key} 必须是数组"
            )
    for index, link in enumerate(data.get("links", [])):
        if not isinstance(link, dict):
            raise HTTPException(status_code=400, detail="备份文件格式错误：links 项必须是对象")
        if not isinstance(link.get("name"), str) or not _is_http_url(link.get("url_lan")):
            raise HTTPException(
                status_code=400,
                detail=f"备份文件格式错误：links[{index}] 缺少合法名称或 http(s) 地址",
            )
    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        raise HTTPException(status_code=400, detail="备份文件格式错误：settings 必须是对象")
    site_settings = data.get("site_settings", {})
    if not isinstance(site_settings, dict):
        raise HTTPException(status_code=400, detail="备份文件格式错误：site_settings 必须是对象")
    return data


def _apply_backup(
    conn: sqlite3.Connection, user: sqlite3.Row, data: dict
) -> dict:
    """追加导入：不删除/覆盖现有数据；分组与链接按新 id 落库。"""
    max_sort = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) AS m FROM groups WHERE user_id = ?",
        (user["id"],),
    ).fetchone()["m"]
    group_id_map: dict[int, int] = {}
    for index, group in enumerate(data.get("groups", [])):
        if not isinstance(group, dict) or not isinstance(group.get("name"), str):
            raise HTTPException(status_code=400, detail="备份文件格式错误：groups 项缺少名称")
        cur = conn.execute(
            "INSERT INTO groups (user_id, name, icon, is_public, sort_order) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                user["id"],
                group["name"],
                group.get("icon"),
                int(bool(group.get("is_public"))),
                max_sort + 1 + index,
            ),
        )
        old_id = group.get("id")
        if isinstance(old_id, int):
            group_id_map[old_id] = int(cur.lastrowid)

    max_link_sort = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) AS m FROM links WHERE user_id = ?",
        (user["id"],),
    ).fetchone()["m"]
    imported_links = 0
    for index, link in enumerate(data.get("links", [])):
        tags = link.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        group_id = link.get("group_id")
        mapped = None
        if isinstance(group_id, int):
            mapped = group_id_map.get(group_id)
        conn.execute(
            "INSERT INTO links (user_id, group_id, name, url_lan, url_wan, icon_type, "
            "icon_value, description, tags, is_public, guest_url_mode, sort_order, open_mode) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user["id"],
                mapped,
                link["name"],
                link["url_lan"],
                link.get("url_wan"),
                link.get("icon_type", "letter"),
                link.get("icon_value"),
                link.get("description", ""),
                json.dumps(tags, ensure_ascii=False),
                int(bool(link.get("is_public"))),
                link.get("guest_url_mode", "hidden"),
                max_link_sort + 1 + index,
                link.get("open_mode", "new_tab"),
            ),
        )
        imported_links += 1

    imported_settings = 0
    for key, value in data.get("settings", {}).items():
        if not isinstance(key, str):
            continue
        conn.execute(
            "INSERT INTO settings (user_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
            (user["id"], key, str(value)),
        )
        imported_settings += 1

    imported_site = 0
    if user["role"] == "admin":
        for key, value in data.get("site_settings", {}).items():
            if not isinstance(key, str):
                continue
            conn.execute(
                "INSERT INTO site_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                "updated_at = datetime('now')",
                (key, str(value)),
            )
            imported_site += 1

    return {
        "groups": len(data.get("groups", [])),
        "links": imported_links,
        "settings": imported_settings,
        "site_settings": imported_site,
    }


@router.get("")
def export_backup(
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> JSONResponse:
    groups = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM groups WHERE user_id = ? ORDER BY sort_order, id",
            (user["id"],),
        ).fetchall()
    ]
    links = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM links WHERE user_id = ? ORDER BY sort_order, id",
            (user["id"],),
        ).fetchall()
    ]
    settings = {
        row["key"]: row["value"]
        for row in conn.execute(
            "SELECT key, value FROM settings WHERE user_id = ?", (user["id"],)
        ).fetchall()
    }
    payload: dict = {
        "version": BACKUP_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "groups": groups,
        "links": links,
        "settings": settings,
    }
    if user["role"] == "admin":
        payload["site_settings"] = {
            row["key"]: row["value"]
            for row in conn.execute("SELECT key, value FROM site_settings").fetchall()
        }
    return JSONResponse(payload)


@router.post("", status_code=201)
def import_backup(
    payload: dict = Body(...),
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    data = _validate_backup(payload)
    return {"imported": _apply_backup(conn, user, data)}


@router.get("/snapshots")
def list_snapshots(
    request: Request,
    user: sqlite3.Row = Depends(current_user),
) -> list[dict]:
    """恢复向导：快照预览条数（管理员）。"""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可查看快照")
    backup_dir = request.app.state.settings.data_dir / "backups"
    if not backup_dir.exists():
        return []
    result: list[dict] = []
    for path in sorted(backup_dir.glob("snapshot-*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        result.append(
            {
                "name": path.name,
                "created_at": data.get("created_at"),
                "groups": len(data.get("groups", [])),
                "links": len(data.get("links", [])),
                "settings": len(data.get("settings", [])),
                "site_settings": len(data.get("site_settings", {})),
            }
        )
    return result


def _snapshot_to_payload(data: dict, user_id: int) -> dict:
    """快照是全量行（含 user_id），恢复时只取当前用户的子集并转为导入格式。"""
    groups = [
        g for g in data.get("groups", [])
        if isinstance(g, dict) and g.get("user_id") == user_id
    ]
    links = [
        l for l in data.get("links", [])
        if isinstance(l, dict) and l.get("user_id") == user_id
    ]
    settings = {
        row["key"]: row["value"]
        for row in data.get("settings", [])
        if isinstance(row, dict)
        and row.get("user_id") == user_id
        and isinstance(row.get("key"), str)
    }
    site = {
        row["key"]: row["value"]
        for row in data.get("site_settings", [])
        if isinstance(row, dict) and isinstance(row.get("key"), str)
    }
    return {"groups": groups, "links": links, "settings": settings, "site_settings": site}


@router.post("/restore/{name}", status_code=201)
def restore_snapshot(
    name: str,
    request: Request,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """从快照文件恢复（追加导入，仅当前用户数据；管理员含站点设置）。"""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可恢复快照")
    if not SNAPSHOT_NAME_RE.fullmatch(name):
        raise HTTPException(status_code=400, detail="快照名称不合法")
    path = request.app.state.settings.data_dir / "backups" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="快照不存在")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="快照文件损坏")
    payload = _snapshot_to_payload(data, user["id"])
    return {"restored": _apply_backup(conn, user, payload)}
