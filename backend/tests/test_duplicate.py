def test_create_duplicate_name_409(client, auth_headers):
    client.post(
        "/api/links", json={"name": "NAS", "url_lan": "http://a.com"}, headers=auth_headers
    )
    r = client.post(
        "/api/links", json={"name": "nas", "url_lan": "http://b.com"}, headers=auth_headers
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "duplicate"


def test_create_duplicate_url_409(client, auth_headers):
    client.post(
        "/api/links", json={"name": "A", "url_lan": "http://a.com"}, headers=auth_headers
    )
    r = client.post(
        "/api/links", json={"name": "B", "url_lan": "http://a.com"}, headers=auth_headers
    )
    assert r.status_code == 409


def test_create_duplicate_force_ok(client, auth_headers):
    client.post(
        "/api/links", json={"name": "A", "url_lan": "http://a.com"}, headers=auth_headers
    )
    r = client.post(
        "/api/links",
        json={"name": "A", "url_lan": "http://a.com", "force": True},
        headers=auth_headers,
    )
    assert r.status_code == 201


def test_update_duplicate_409(client, auth_headers):
    client.post(
        "/api/links", json={"name": "A", "url_lan": "http://a.com"}, headers=auth_headers
    )
    lid = client.post(
        "/api/links", json={"name": "B", "url_lan": "http://b.com"}, headers=auth_headers
    ).json()["id"]
    r = client.put(
        f"/api/links/{lid}",
        json={"name": "A", "url_lan": "http://b.com"},
        headers=auth_headers,
    )
    assert r.status_code == 409


def test_update_self_no_conflict(client, auth_headers):
    lid = client.post(
        "/api/links", json={"name": "A", "url_lan": "http://a.com"}, headers=auth_headers
    ).json()["id"]
    r = client.put(
        f"/api/links/{lid}",
        json={"name": "A", "url_lan": "http://a.com"},
        headers=auth_headers,
    )
    assert r.status_code == 200
