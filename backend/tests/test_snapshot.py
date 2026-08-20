def _snapshots(client):
    import json
    from pathlib import Path

    backup_dir = Path(client.app.state.settings.data_dir) / "backups"
    if not backup_dir.exists():
        return []
    return sorted(backup_dir.glob("snapshot-*.json"))


def test_snapshot_created_on_mutation(client, auth_headers):
    client.post(
        "/api/groups", json={"name": "工作", "is_public": True}, headers=auth_headers
    )
    snaps = _snapshots(client)
    assert len(snaps) == 1
    import json

    data = json.loads(snaps[0].read_text())
    assert data["groups"][0]["name"] == "工作"


def test_snapshot_prune_keeps_latest(client, tmp_path):
    from fastapi.testclient import TestClient

    from app.config import load_settings
    from app.main import create_app

    app = create_app(
        load_settings(
            overrides={"data_dir": str(tmp_path), "secret_key": "x", "backup_keep": 2}
        )
    )
    c = TestClient(app)
    c.post("/api/setup", json={"username": "admin", "password": "secret123"})
    login = c.post("/api/auth/login", json={"username": "admin", "password": "secret123"})
    headers = {"Cookie": f"lipanel_session={login.cookies['lipanel_session']}"}
    for i in range(3):
        c.post("/api/groups", json={"name": f"G{i}"}, headers=headers)
    snaps = sorted((tmp_path / "backups").glob("snapshot-*.json"))
    assert len(snaps) == 2


def test_snapshot_not_created_on_login(client, auth_headers):
    assert _snapshots(client) == []
