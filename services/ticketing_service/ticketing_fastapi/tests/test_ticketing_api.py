import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////tmp/gx_ticketing_service_tests.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"

import app.main as ticketing_main  # noqa: E402
from app.database import Base, sync_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.security import get_current_user  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)


@pytest.fixture
def client(monkeypatch):
    async def fake_connect():
        return None

    async def fake_close():
        return None

    async def fake_publish(event_type, payload):
        return True

    monkeypatch.setattr(ticketing_main.broker, "connect", fake_connect)
    monkeypatch.setattr(ticketing_main.broker, "close", fake_close)
    monkeypatch.setattr(ticketing_main.broker, "publish", fake_publish)

    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": 1,
        "email": "fan@example.com",
        "first_name": "Alex",
        "last_name": "Fan",
        "access_token": "test-token",
    }

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def match_info(match_id=101, seats_available=10):
    return {
        "match_id": match_id,
        "seats_available": seats_available,
        "unit_price": Decimal("1500.00"),
        "currency": "RUB",
        "status": "scheduled",
    }


def test_match_availability(client, monkeypatch):
    async def fake_fetch(match_id):
        return match_info(match_id=match_id, seats_available=50)

    monkeypatch.setattr(ticketing_main, "fetch_match_ticketing_info", fake_fetch)

    response = client.get("/matches/101/availability")

    assert response.status_code == 200
    assert response.json()["match_id"] == 101
    assert response.json()["available_seats"] == 50
    assert response.json()["can_reserve"] is True


def test_create_confirm_and_cancel_booking(client, monkeypatch):
    async def fake_fetch(match_id):
        return match_info(match_id=match_id, seats_available=10)

    async def fake_create_payment(booking, access_token):
        return {
            "payment_id": "pay_test",
            "payment_url": "http://localhost/payments/pay_test",
            "status": "pending",
        }

    monkeypatch.setattr(ticketing_main, "fetch_match_ticketing_info", fake_fetch)
    monkeypatch.setattr(ticketing_main, "create_payment_for_booking", fake_create_payment)

    create_response = client.post(
        "/bookings",
        json={"match_id": 101, "quantity": 2},
    )

    assert create_response.status_code == 201
    booking = create_response.json()
    assert booking["status"] == "pending_payment"
    assert booking["payment_id"] == "pay_test"

    confirm_response = client.post(
        f"/bookings/{booking['id']}/confirm",
        json={"payment_reference": "pay_test"},
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "confirmed"

    cancel_response = client.delete(f"/bookings/{booking['id']}")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"


def test_metrics_endpoint_records_requests(client, monkeypatch):
    async def fake_fetch(match_id):
        return match_info(match_id=match_id, seats_available=5)

    monkeypatch.setattr(ticketing_main, "fetch_match_ticketing_info", fake_fetch)
    client.get("/matches/101/availability")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "gx_http_requests_total" in response.text
    assert "gx_ticketing_booking_events_total" in response.text
