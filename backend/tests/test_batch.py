def _ids(client, auth_headers, names):
    return [
        client.post(
            "/api/links",
            json={"name": n, "url_lan": f"http://{n}.com"},
            headers=auth_headers,
        ).json()["id"]
        for n in names
    ]


def test_batch_delete(client, auth_headers):
    ids = _ids(client, auth_headers, ["A", "B", "C"])
    r = client.post(
        "/api/links/batch-delete", json={"ids": ids[:2]}, headers=auth_headers
    )
    assert r.status_code == 200 and r.json() == {"deleted": 2}
    remain = client.get("/api/links", headers=auth_headers).json()
    assert [l["id"] for l in remain] == [ids[2]]


def test_batch_move(client, auth_headers):
    ids = _ids(client, auth_headers, ["A", "B"])
    gid = client.post("/api/groups", json={"name": "G"}, headers=auth_headers).json()["id"]
    r = client.post(
        "/api/links/batch-move",
        json={"ids": ids, "group_id": gid},
        headers=auth_headers,
    )
    assert r.status_code == 200 and r.json() == {"moved": 2}
    links = client.get("/api/links", headers=auth_headers).json()
    assert all(l["group_id"] == gid for l in links)


def test_batch_move_ungroup(client, auth_headers):
    ids = _ids(client, auth_headers, ["A"])
    r = client.post(
        "/api/links/batch-move", json={"ids": ids, "group_id": None},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert client.get("/api/links", headers=auth_headers).json()[0]["group_id"] is None


def test_batch_visibility(client, auth_headers):
    ids = _ids(client, auth_headers, ["A", "B"])
    r = client.post(
        "/api/links/batch-visibility",
        json={"ids": ids, "is_public": True},
        headers=auth_headers,
    )
    assert r.status_code == 200 and r.json() == {"updated": 2}
    links = client.get("/api/links", headers=auth_headers).json()
    assert all(bool(l["is_public"]) for l in links)


def test_batch_empty_rejected(client, auth_headers):
    assert (
        client.post("/api/links/batch-delete", json={"ids": []}, headers=auth_headers).status_code
        == 422
    )


def test_batch_foreign_404(client, auth_headers):
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
    lid = client.post(
        "/api/links", json={"name": "A", "url_lan": "http://a.com"}, headers=auth_headers
    ).json()["id"]
    assert (
        client.post("/api/links/batch-delete", json={"ids": [lid]}, headers=bh).status_code
        == 404
    )
