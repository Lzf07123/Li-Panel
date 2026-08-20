import urllib.parse


def _create(client, auth_headers, name, tags):
    return client.post(
        "/api/links",
        json={"name": name, "url_lan": f"http://{name}.com", "tags": tags},
        headers=auth_headers,
    )


def test_tags_stats(client, auth_headers):
    _create(client, auth_headers, "A", ["开发", "前端"])
    _create(client, auth_headers, "B", ["开发"])
    r = client.get("/api/tags", headers=auth_headers)
    assert r.status_code == 200
    assert {t["name"]: t["count"] for t in r.json()} == {"前端": 1, "开发": 2}


def test_tag_rename_updates_all(client, auth_headers):
    _create(client, auth_headers, "A", ["开发", "前端"])
    _create(client, auth_headers, "B", ["开发"])
    tag = urllib.parse.quote("开发")
    r = client.put(f"/api/tags/{tag}", json={"name": "工程"}, headers=auth_headers)
    assert r.status_code == 200 and r.json() == {"renamed": 2}
    links = client.get("/api/links", headers=auth_headers).json()
    assert all("工程" in l["tags"] for l in links)
    assert all("开发" not in l["tags"] for l in links)


def test_tag_delete(client, auth_headers):
    _create(client, auth_headers, "A", ["开发", "前端"])
    tag = urllib.parse.quote("前端")
    r = client.delete(f"/api/tags/{tag}", headers=auth_headers)
    assert r.status_code == 200 and r.json() == {"removed": 1}
    links = client.get("/api/links", headers=auth_headers).json()
    assert links[0]["tags"] == ["开发"]


def test_tag_rename_same_rejected(client, auth_headers):
    _create(client, auth_headers, "A", ["开发"])
    tag = urllib.parse.quote("开发")
    assert (
        client.put(f"/api/tags/{tag}", json={"name": "开发"}, headers=auth_headers).status_code
        == 400
    )


def test_tag_requires_auth(client):
    assert client.get("/api/tags").status_code == 401


def test_tag_isolation(client, auth_headers):
    from app.db import connect
    from app.security import hash_password

    _create(client, auth_headers, "A", ["私有标签"])
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
    tags = client.get("/api/tags", headers=bh).json()
    assert tags == []
