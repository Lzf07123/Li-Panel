def test_lockout_after_max_fails(client, auth_headers):
    for _ in range(5):
        r = client.post(
            "/api/auth/login", json={"username": "admin", "password": "wrong"}
        )
        assert r.status_code == 401
    # 第 6 次即使密码正确也被锁
    r = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )
    assert r.status_code == 429
    assert "分钟" in r.json()["detail"]


def test_lockout_success_resets(client, auth_headers):
    for _ in range(3):
        client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    r = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )
    assert r.status_code == 200
    # 重置后再次失败：第 5 次失败达阈值（当次 401），第 6 次起锁定
    for _ in range(5):
        assert (
            client.post(
                "/api/auth/login", json={"username": "admin", "password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login", json={"username": "admin", "password": "wrong"}
        ).status_code
        == 429
    )


def test_lockout_unknown_user_same_behavior(client):
    for _ in range(5):
        r = client.post(
            "/api/auth/login", json={"username": "ghost", "password": "wrong"}
        )
        assert r.status_code == 401
    assert (
        client.post(
            "/api/auth/login", json={"username": "ghost", "password": "wrong"}
        ).status_code
        == 429
    )


def test_lockout_configurable(client, tmp_path):
    from fastapi.testclient import TestClient

    from app.config import load_settings
    from app.main import create_app

    app = create_app(
        load_settings(
            overrides={
                "data_dir": str(tmp_path),
                "secret_key": "x",
                "login_max_fails": 2,
                "login_lock_minutes": 15,
            }
        )
    )
    c = TestClient(app)
    c.post("/api/setup", json={"username": "admin", "password": "secret123"})
    for _ in range(2):
        c.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert (
        c.post(
            "/api/auth/login", json={"username": "admin", "password": "secret123"}
        ).status_code
        == 429
    )


def test_lockout_expires_after_window(monkeypatch):
    """上线前修复：锁定窗口结束后必须自动解除，不能永久锁死。"""
    import app.security as sec

    clock = {"now": 1000.0}
    monkeypatch.setattr(sec.time, "monotonic", lambda: clock["now"])
    lk = sec.LoginLockout(max_fails=2, lock_minutes=1)
    lk.record_failure("admin", "1.2.3.4")
    lk.record_failure("admin", "1.2.3.4")
    assert lk.is_locked("admin", "1.2.3.4")
    clock["now"] += 61
    assert not lk.is_locked("admin", "1.2.3.4")
    # 解锁后重新计数，仍能再次锁定
    lk.record_failure("admin", "1.2.3.4")
    assert not lk.is_locked("admin", "1.2.3.4")
    lk.record_failure("admin", "1.2.3.4")
    assert lk.is_locked("admin", "1.2.3.4")
