def test_link_crud(client, auth_headers):
    r = client.post(
        "/api/links",
        json={"name": "路由器", "url_lan": "http://192.168.1.1"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    lid = r.json()["id"]
    r2 = client.put(
        f"/api/links/{lid}",
        json={"name": "NAS", "url_lan": "http://192.168.1.2"},
        headers=auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["name"] == "NAS"
    assert client.delete(f"/api/links/{lid}", headers=auth_headers).status_code == 204


def test_link_invalid_url(client, auth_headers):
    r = client.post(
        "/api/links",
        json={"name": "x", "url_lan": "ftp://bad"},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_link_group_must_be_owned(client, auth_headers):
    r = client.post(
        "/api/links",
        json={"name": "x", "url_lan": "http://x.com", "group_id": 999},
        headers=auth_headers,
    )
    assert r.status_code == 404


def test_link_order_rewrites_sort(client, auth_headers):
    ids = []
    for name in ["A", "B", "C"]:
        r = client.post(
            "/api/links",
            json={"name": name, "url_lan": f"http://x{name}.com"},
            headers=auth_headers,
        )
        ids.append(r.json()["id"])
    r = client.patch(
        "/api/links/order", json={"ordered_ids": [ids[2], ids[0], ids[1]]},
        headers=auth_headers,
    )
    assert r.status_code == 200
    ordered = [l["id"] for l in client.get("/api/links", headers=auth_headers).json()]
    assert ordered == [ids[2], ids[0], ids[1]]


def test_link_order_subset_ok(client, auth_headers):
    ids = []
    for name in ["A", "B", "C"]:
        r = client.post(
            "/api/links",
            json={"name": name, "url_lan": f"http://x{name}.com"},
            headers=auth_headers,
        )
        ids.append(r.json()["id"])
    r = client.patch(
        "/api/links/order", json={"ordered_ids": [ids[1], ids[0]]},
        headers=auth_headers,
    )
    assert r.status_code == 200
    ordered = [l["id"] for l in client.get("/api/links", headers=auth_headers).json()]
    assert ordered[:2] == [ids[1], ids[0]]


def test_link_order_duplicate_rejected(client, auth_headers):
    r = client.post(
        "/api/links",
        json={"name": "A", "url_lan": "http://a.com"},
        headers=auth_headers,
    )
    lid = r.json()["id"]
    assert (
        client.patch(
            "/api/links/order", json={"ordered_ids": [lid, lid]}, headers=auth_headers
        ).status_code
        == 400
    )


def test_link_order_requires_auth(client):
    assert (
        client.patch("/api/links/order", json={"ordered_ids": [1]}).status_code == 401
    )
