import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["DATABASE_URL"] = "sqlite:////tmp/gx_auth_service_tests.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def client(monkeypatch):
    async def fake_publish(payload):
        return None

    monkeypatch.setattr(
        "app.main.broker.publish_user_registered_event",
        fake_publish,
    )
    return TestClient(app)


def test_register_login_and_profile_not_ready(client):
    register_response = client.post(
        "/register",
        json={
            "email": "fan@example.com",
            "password": "secret123",
            "first_name": "Alex",
            "last_name": "Fan",
        },
    )

    assert register_response.status_code == 201
    token = register_response.json()["access_token"]
    assert token

    duplicate_response = client.post(
        "/register",
        json={
            "email": "fan@example.com",
            "password": "secret123",
            "first_name": "Alex",
            "last_name": "Fan",
        },
    )
    assert duplicate_response.status_code == 400

    login_response = client.post(
        "/login",
        json={"email": "fan@example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["access_token"]

    profile_response = client.get(
        "/profiles/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert profile_response.status_code == 404


def test_metrics_endpoint_records_requests(client):
    client.get("/")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "gx_http_requests_total" in response.text
    assert "gx_auth_registrations_total" in response.text
