from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import create_app


@pytest.fixture
def app(tmp_path):
    settings = load_settings(
        overrides={
            "data_dir": str(tmp_path),
            "secret_key": "test-secret",
            "public_mode": True,
        }
    )
    return create_app(settings)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def admin(client):
    response = client.post(
        "/api/setup", json={"username": "admin", "password": "secret123"}
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def auth_headers(client, admin):
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )
    assert response.status_code == 200
    return {"Cookie": f"lipanel_session={response.cookies['lipanel_session']}"}
