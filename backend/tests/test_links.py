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
