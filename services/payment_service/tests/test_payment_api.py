import asyncio
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////tmp/gx_payment_service_tests.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672/"

import app.main as payment_main  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app, get_current_user, get_rmq  # noqa: E402


async def recreate_database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


@pytest.fixture(autouse=True)
def reset_database():
    asyncio.run(recreate_database())


@pytest.fixture
def client(monkeypatch):
    async def fake_publish(connection, routing_key, data):
        return None

    class FakeRabbitConnection:
        async def close(self):
            return None

    async def fake_connect_robust(*args, **kwargs):
        return FakeRabbitConnection()

    monkeypatch.setattr(payment_main, "publish_payment_event", fake_publish)
    monkeypatch.setattr(payment_main.aio_pika, "connect_robust", fake_connect_robust)

    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": 1,
        "email": "fan@example.com",
        "first_name": "Alex",
        "last_name": "Fan",
    }
    app.dependency_overrides[get_rmq] = lambda: FakeRabbitConnection()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def payment_payload(order_id):
    return {
        "order_id": order_id,
        "amount": "3000.00",
        "currency": "RUB",
        "description": "Tickets",
        "success_url": "http://localhost/success",
        "fail_url": "http://localhost/fail",
        "webhook_url": "http://localhost/webhook",
    }


def create_payment(client, order_id=1):
    response = client.post("/payments", json=payment_payload(order_id))
    assert response.status_code == 201
    return response.json()


def test_create_get_pay_and_fail_payment(client):
    created = create_payment(client, order_id=1)
    payment_id = created["payment_id"]
    assert created["status"] == "pending"

    get_response = client.get(f"/payments/{payment_id}")
    assert get_response.status_code == 200
    assert get_response.json()["payment_id"] == payment_id

    pay_response = client.post(f"/payments/{payment_id}/pay")
    assert pay_response.status_code == 200
    assert pay_response.json()["status"] == "paid"
    assert pay_response.json()["signature"]

    failed_payment = create_payment(client, order_id=2)
    fail_response = client.post(f"/payments/{failed_payment['payment_id']}/fail")
    assert fail_response.status_code == 200
    assert fail_response.json()["status"] == "failed"


def test_metrics_endpoint_records_requests(client):
    client.get("/health")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "gx_http_requests_total" in response.text
    assert "gx_payment_status_changes_total" in response.text
