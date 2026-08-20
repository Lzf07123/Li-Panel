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
