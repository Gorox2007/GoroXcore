import hashlib
from contextlib import asynccontextmanager

import aio_pika
from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker.publisher import publish_payment_event
from app.config import settings
from app.crud import (
    create_payment,
    get_payment_by_payment_id,
    mark_payment_failed,
    mark_payment_paid,
)
from app.db import get_db
from app.schemas import (
    PaymentCreate,
    PaymentCreateResponse,
    PaymentStatusResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.rmq_connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    yield
    await app.state.rmq_connection.close()


app = FastAPI(
    title="Payment Service",
    description="Payment microservice for football ticket booking",
    version="1.0.0",
    lifespan=lifespan,
)


def get_rmq(request: Request) -> aio_pika.RobustConnection:
    return request.app.state.rmq_connection


@app.get("/health")
async def healthcheck():
    return {"status": "ok"}


@app.post("/payments", response_model=PaymentCreateResponse, status_code=201)
async def create_payment_endpoint(
    payload: PaymentCreate,
    db: AsyncSession = Depends(get_db),
):
    payment = await create_payment(db, payload)
    return {
        "payment_id": payment.payment_id,
        "status": payment.status,
        "order_id": payment.order_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "payment_url": f"http://localhost:8000/payments/{payment.payment_id}",
        "created_at": payment.created_at,
    }


@app.get("/payments/{payment_id}", response_model=PaymentStatusResponse)
async def get_payment_endpoint(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
):
    payment = await get_payment_by_payment_id(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {
        "payment_id": payment.payment_id,
        "status": payment.status,
        "order_id": payment.order_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "paid_at": payment.paid_at,
        "signature": payment.signature,
    }


@app.post("/payments/{payment_id}/pay", response_model=PaymentStatusResponse)
async def pay_payment_endpoint(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
    rmq: aio_pika.RobustConnection = Depends(get_rmq),
):
    payment = await get_payment_by_payment_id(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status == "paid":
        return {
            "payment_id": payment.payment_id,
            "status": payment.status,
            "order_id": payment.order_id,
            "amount": payment.amount,
            "currency": payment.currency,
            "paid_at": payment.paid_at,
            "signature": payment.signature,
        }

    signature = hashlib.sha256(
        f"{payment.payment_id}:{payment.order_id}:{payment.amount}".encode()
    ).hexdigest()

    payment = await mark_payment_paid(db, payment_id, signature)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    event_data = {
        "payment_id": payment.payment_id,
        "order_id": payment.order_id,
        "status": payment.status,
        "amount": float(payment.amount),
        "currency": payment.currency,
        "paid_at": payment.paid_at.isoformat() + "Z" if payment.paid_at else None,
        "signature": payment.signature,
    }

    try:
        await publish_payment_event(rmq, "payment.completed", event_data)
    except Exception as e:
        print(f"RabbitMQ publish error: {e}")

    return event_data


@app.post("/payments/{payment_id}/fail", response_model=PaymentStatusResponse)
async def fail_payment_endpoint(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
    rmq: aio_pika.RobustConnection = Depends(get_rmq),
):
    payment = await mark_payment_failed(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    event_data = {
        "payment_id": payment.payment_id,
        "order_id": payment.order_id,
        "status": payment.status,
        "amount": float(payment.amount),
        "currency": payment.currency,
        "paid_at": None,
        "signature": None,
    }

    try:
        await publish_payment_event(rmq, "payment.failed", event_data)
    except Exception as e:
        print(f"RabbitMQ publish error: {e}")

    return {
        "payment_id": payment.payment_id,
        "status": payment.status,
        "order_id": payment.order_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "paid_at": payment.paid_at,
        "signature": payment.signature,
    }
