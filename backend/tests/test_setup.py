def test_setup_first_and_second(client):
    assert client.get("/api/setup-status").json()["required"] is True
    r = client.post("/api/setup", json={"username": "admin", "password": "secret123"})
    assert r.status_code == 201
    assert client.get("/api/setup-status").json()["required"] is False
    r2 = client.post("/api/setup", json={"username": "userb", "password": "secret123"})
    assert r2.status_code == 409


def test_setup_rejects_bad_username(client):
    r = client.post("/api/setup", json={"username": "ab", "password": "secret123"})
    assert r.status_code == 422
