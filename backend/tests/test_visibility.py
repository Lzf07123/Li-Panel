def test_guest_sees_only_public(client, auth_headers):
    client.post(
        "/api/groups", json={"name": "公开组", "is_public": True}, headers=auth_headers
    )
    client.post("/api/groups", json={"name": "私密组"}, headers=auth_headers)
    client.post("/api/auth/logout")
    r = client.get("/api/panel")
    assert r.status_code == 200
    assert [g["name"] for g in r.json()["groups"]] == ["公开组"]


def test_go_hides_url_for_guest(client, auth_headers):
    r = client.post(
        "/api/links",
        json={
            "name": "NAS",
            "url_lan": "http://192.168.1.2",
            "is_public": True,
        },
        headers=auth_headers,
    )
    lid = r.json()["id"]
    client.post("/api/auth/logout")
    panel = client.get("/api/panel").json()
    links = panel["ungrouped"]
    assert "url_lan" not in links[0] and "url_wan" not in links[0]
    redir = client.get(f"/go/{lid}", follow_redirects=False)
    assert redir.status_code == 302
    assert redir.headers["location"] == "http://192.168.1.2"
    assert client.get(f"/go/{lid + 999}").status_code == 404


def test_private_link_not_goable(client, auth_headers):
    r = client.post(
        "/api/links",
        json={"name": "内网", "url_lan": "http://10.0.0.1"},
        headers=auth_headers,
    )
    lid = r.json()["id"]
    assert client.get(f"/go/{lid}").status_code == 404
