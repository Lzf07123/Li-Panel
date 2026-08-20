def test_group_crud(client, auth_headers):
    r = client.post(
        "/api/groups", json={"name": "工作", "is_public": True}, headers=auth_headers
    )
    assert r.status_code == 201
    gid = r.json()["id"]
    groups = client.get("/api/groups", headers=auth_headers).json()
    assert groups[0]["name"] == "工作"
    assert client.put(
        f"/api/groups/{gid}", json={"name": "生活"}, headers=auth_headers
    ).status_code == 200
    assert client.delete(f"/api/groups/{gid}", headers=auth_headers).status_code == 204


def test_group_requires_auth(client):
    assert client.post("/api/groups", json={"name": "x"}).status_code == 401


def test_group_order_rewrites_sort(client, auth_headers):
    ids = []
    for name in ["A", "B", "C"]:
        r = client.post(
            "/api/groups", json={"name": name, "is_public": True}, headers=auth_headers
        )
        ids.append(r.json()["id"])
    r = client.patch(
        "/api/groups/order", json={"ordered_ids": [ids[2], ids[0], ids[1]]},
        headers=auth_headers,
    )
    assert r.status_code == 200
    ordered = [g["id"] for g in client.get("/api/groups", headers=auth_headers).json()]
    assert ordered == [ids[2], ids[0], ids[1]]


def test_group_order_subset_ok(client, auth_headers):
    ids = []
    for name in ["A", "B", "C"]:
        r = client.post(
            "/api/groups", json={"name": name}, headers=auth_headers
        )
        ids.append(r.json()["id"])
    r = client.patch(
        "/api/groups/order", json={"ordered_ids": [ids[1], ids[0]]},
        headers=auth_headers,
    )
    assert r.status_code == 200
    ordered = [g["id"] for g in client.get("/api/groups", headers=auth_headers).json()]
    assert ordered[:2] == [ids[1], ids[0]]


def test_group_order_duplicate_rejected(client, auth_headers):
    r = client.post("/api/groups", json={"name": "A"}, headers=auth_headers)
    gid = r.json()["id"]
    assert (
        client.patch(
            "/api/groups/order", json={"ordered_ids": [gid, gid]}, headers=auth_headers
        ).status_code
        == 400
    )


def test_group_order_requires_auth(client):
    assert (
        client.patch("/api/groups/order", json={"ordered_ids": [1]}).status_code == 401
    )


def test_group_icon_roundtrip(client, auth_headers):
    r = client.post(
        "/api/groups",
        json={"name": "工作", "icon": "folder", "is_public": True},
        headers=auth_headers,
    )
    assert r.status_code == 201
    gid = r.json()["id"]
    assert r.json()["icon"] == "folder"
    r2 = client.put(
        f"/api/groups/{gid}",
        json={"name": "工作", "icon": "code", "is_public": True},
        headers=auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["icon"] == "code"


def test_group_icon_persisted_when_toggling_visibility(client, auth_headers):
    r = client.post(
        "/api/groups",
        json={"name": "工作", "icon": "cloud", "is_public": True},
        headers=auth_headers,
    )
    gid = r.json()["id"]
    client.put(
        f"/api/groups/{gid}",
        json={"name": "工作", "icon": "cloud", "is_public": False},
        headers=auth_headers,
    )
    groups = client.get("/api/groups", headers=auth_headers).json()
    assert groups[0]["icon"] == "cloud"
