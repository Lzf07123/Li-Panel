from __future__ import annotations

import json
import sqlite3
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import get_db
from app.deps import current_user

router = APIRouter(prefix="/api/tags", tags=["tags"])

TAG_MAX_LEN = 30


def _clean_tag(value: str) -> str:
    tag = value.strip()
    if not tag:
        raise HTTPException(status_code=400, detail="标签不能为空")
    if len(tag) > TAG_MAX_LEN:
        raise HTTPException(status_code=400, detail=f"标签最长 {TAG_MAX_LEN} 个字符")
    return tag


def _user_links(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, tags FROM links WHERE user_id = ?", (user_id,)
    ).fetchall()


@router.get("")
def list_tags(
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    counter: Counter[str] = Counter()
    for row in _user_links(conn, user["id"]):
        counter.update(json.loads(row["tags"] or "[]"))
    return [
        {"name": name, "count": count}
        for name, count in sorted(counter.items(), key=lambda item: item[0])
    ]


class RenameTagIn(BaseModel):
    name: str = Field(min_length=1, max_length=TAG_MAX_LEN)


@router.put("/{tag}")
def rename_tag(
    tag: str,
    body: RenameTagIn,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    old = _clean_tag(tag)
    new = _clean_tag(body.name)
    if old == new:
        raise HTTPException(status_code=400, detail="新旧标签相同")
    updated = 0
    for row in _user_links(conn, user["id"]):
        tags = json.loads(row["tags"] or "[]")
        if old not in tags:
            continue
        next_tags = [new if t == old else t for t in tags]
        # 去重并保持原顺序
        seen: set[str] = set()
        deduped: list[str] = []
        for t in next_tags:
            if t not in seen:
                seen.add(t)
                deduped.append(t)
        conn.execute(
            "UPDATE links SET tags = ? WHERE id = ? AND user_id = ?",
            (json.dumps(deduped, ensure_ascii=False), row["id"], user["id"]),
        )
        updated += 1
    return {"renamed": updated}


@router.delete("/{tag}", status_code=200)
def delete_tag(
    tag: str,
    user: sqlite3.Row = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    target = _clean_tag(tag)
    removed = 0
    for row in _user_links(conn, user["id"]):
        tags = json.loads(row["tags"] or "[]")
        if target not in tags:
            continue
        next_tags = [t for t in tags if t != target]
        conn.execute(
            "UPDATE links SET tags = ? WHERE id = ? AND user_id = ?",
            (json.dumps(next_tags, ensure_ascii=False), row["id"], user["id"]),
        )
        removed += 1
    return {"removed": removed}
