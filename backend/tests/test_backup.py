def _setup_data(client, auth_headers):
    gid = client.post(
        "/api/groups", json={"name": "工作", "icon": "folder", "is_public": True},
        headers=auth_headers,
    ).json()["id"]
    client.post(
        "/api/links",
        json={"name": "NAS", "url_lan": "http://192.168.1.2", "group_id": gid, "tags": ["内网"]},
        headers=auth_headers,
    )
    client.put(
        "/api/settings", json={"link_mode": "wan"}, headers=auth_headers
    )


def test_backup_export_contains_own_data(client, auth_headers):
    _setup_data(client, auth_headers)
    r = client.get("/api/backup", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == 1
    assert data["groups"][0]["name"] == "工作"
    assert data["links"][0]["url_lan"] == "http://192.168.1.2"
    assert data["settings"]["link_mode"] == "wan"
    assert "site_settings" in data  # admin 角色


def test_backup_import_appends(client, auth_headers):
    _setup_data(client, auth_headers)
    before_links = len(client.get("/api/links", headers=auth_headers).json())
    backup = client.get("/api/backup", headers=auth_headers).json()
    r = client.post("/api/backup", json=backup, headers=auth_headers)
    assert r.status_code == 201
    assert r.json()["imported"]["groups"] == 1
    assert r.json()["imported"]["links"] == 1
    after_links = client.get("/api/links", headers=auth_headers).json()
    assert len(after_links) == before_links + 1
    # 同名分组合并复用：分组数不变，链接挂到原分组
    new_groups = client.get("/api/groups", headers=auth_headers).json()
    assert len(new_groups) == 1
    assert after_links[-1]["group_id"] == new_groups[0]["id"]


def test_backup_import_rejects_bad_url(client, auth_headers):
    bad = {"version": 1, "groups": [], "links": [{"name": "x", "url_lan": "ftp://bad"}], "settings": {}}
    assert client.post("/api/backup", json=bad, headers=auth_headers).status_code == 400


def test_backup_import_rejects_bad_structure(client, auth_headers):
    assert client.post("/api/backup", json={"groups": "x"}, headers=auth_headers).status_code == 400


def test_backup_isolation(client, auth_headers):
    from app.db import connect
    from app.security import hash_password

    _setup_data(client, auth_headers)
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
    backup = client.get("/api/backup", headers=bh).json()
    assert backup["groups"] == [] and backup["links"] == []
    assert "site_settings" not in backup  # 普通用户不含站点设置


def test_backup_requires_auth(client):
    assert client.get("/api/backup").status_code == 401


def test_backup_import_dedupes_groups(client, auth_headers):
    _setup_data(client, auth_headers)  # 1 组 1 链接
    backup = client.get("/api/backup", headers=auth_headers).json()
    client.post("/api/backup", json=backup, headers=auth_headers)
    client.post("/api/backup", json=backup, headers=auth_headers)
    groups = client.get("/api/groups", headers=auth_headers).json()
    assert len(groups) == 1  # 同名分组合并，不产生重复
    links = client.get("/api/links", headers=auth_headers).json()
    assert len(links) == 3  # 链接仍按追加语义进入
    assert all(link["group_id"] == groups[0]["id"] for link in links)
