"""自动快照：数据变更后写 data/backups/snapshot-{ts}.json，滚动保留最近 N 份。

快照内容：全量 groups/links/settings/site_settings（不含用户与会话），
供恢复向导预览与追加导入。写盘失败不影响主流程。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.db import connect


def write_snapshot(data_dir: Path, db_path: Path, keep: int) -> None:
    try:
        conn = connect(db_path)
        groups = [dict(r) for r in conn.execute("SELECT * FROM groups").fetchall()]
        links = [dict(r) for r in conn.execute("SELECT * FROM links").fetchall()]
        settings = [
            dict(r) for r in conn.execute("SELECT * FROM settings").fetchall()
        ]
        site_settings = [
            dict(r) for r in conn.execute("SELECT * FROM site_settings").fetchall()
        ]
        conn.close()
    except sqlite3.Error:
        return
    payload = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "groups": groups,
        "links": links,
        "settings": settings,
        "site_settings": site_settings,
    }
    backup_dir = data_dir / "backups"
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        (backup_dir / f"snapshot-{stamp}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        snapshots = sorted(backup_dir.glob("snapshot-*.json"))
        for old in snapshots[:-keep] if keep > 0 else snapshots:
            old.unlink(missing_ok=True)
    except OSError:
        return
