def _make_snapshot(client, auth_headers):
    gid = client.post(
        "/api/groups", json={"name": "快照组", "icon": "star"}, headers=auth_headers
    ).json()["id"]
    client.post(
        "/api/links",
        json={"name": "NAS", "url_lan": "http://192.168.1.9", "group_id": gid},
        headers=auth_headers,
    )
    import json
    from pathlib import Path

    backup_dir = Path(client.app.state.settings.data_dir) / "backups"
    return sorted(backup_dir.glob("snapshot-*.json"))[-1]


def test_snapshot_list_and_restore(client, auth_headers):
    snap = _make_snapshot(client, auth_headers)
    snaps = client.get("/api/backup/snapshots", headers=auth_headers)
    assert snaps.status_code == 200
    assert snaps.json()[0]["name"] == snap.name
    assert snaps.json()[0]["links"] == 1
    before = len(client.get("/api/links", headers=auth_headers).json())
    r = client.post(
        f"/api/backup/restore/{snap.name}", headers=auth_headers
    )
    assert r.status_code == 201
    assert r.json()["restored"]["links"] == 1
    after = client.get("/api/links", headers=auth_headers).json()
    assert len(after) == before + 1
    assert after[-1]["name"] == "NAS"


def test_snapshot_restore_bad_name(client, auth_headers):
    assert (
        client.post("/api/backup/restore/snapshot-evil!.json", headers=auth_headers).status_code
        == 400
    )


def test_snapshot_restore_missing(client, auth_headers):
    assert (
        client.post("/api/backup/restore/snapshot-nope.json", headers=auth_headers).status_code
        == 404
    )


def test_snapshot_list_requires_admin(client, auth_headers):
    from app.db import connect
    from app.security import hash_password

    conn = connect(client.app.state.db_path)
    ph, salt = hash_password("secret123")
    conn.execute(
        "INSERT INTO users (username, password_hash, salt, role) VALUES ('user_b', ?, ?, 'user')",
        (ph, salt),
    )
    conn.commit()
    conn.close()
    b = client.post(
        "/api/auth/login", json={"username": "user_b", "password": "secret123"}
    )
    bh = {"Cookie": f"lipanel_session={b.cookies['lipanel_session']}"}
    assert client.get("/api/backup/snapshots", headers=bh).status_code == 403
