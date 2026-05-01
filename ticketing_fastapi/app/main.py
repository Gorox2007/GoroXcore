from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging

from fastapi import Body, Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models, schemas
from .broker import broker
from .database import SessionLocal
from .payment_client import create_payment

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Ticketing Service API",
    description=(
        "Сервис бронирования билетов на матчи. Оплата обрабатывается "
        "внешней системой; этот API только создаёт и управляет бронированиями."
    ),
    version="1.0.0",
)


async def get_db():
    async with SessionLocal() as db:
        yield db


@app.on_event("startup")
async def on_startup():
    try:
        await broker.connect()
    except Exception:
        logger.exception("RabbitMQ недоступен на старте. API продолжит работу без брокера.")


@app.on_event("shutdown")
async def on_shutdown():
    await broker.close()


def error_response(status_code: int, message: str, details: str | None = None):
    payload = {"error": message, "code": status_code}
    if details:
        payload["details"] = details
    return JSONResponse(status_code=status_code, content=payload)


def parse_int(value: str, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} должен быть целым числом")


def booking_to_out(booking: models.Booking, payment_url: str | None = None) -> dict:
    return {
        "id": booking.id,
        "match_id": booking.match_id,
        "customer_name": booking.customer_name,
        "customer_email": booking.customer_email,
        "quantity": booking.quantity,
        "unit_price": float(booking.unit_price),
        "total_price": float(booking.total_price),
        "currency": booking.currency,
        "status": booking.status,
        "reserved_at": booking.reserved_at,
        "expires_at": booking.expires_at,
        "payment_reference": booking.payment_reference,
        "payment_url": payment_url,
    }


def availability_to_out(inventory: models.MatchInventory) -> dict:
    available = max(inventory.capacity - inventory.reserved, 0)
    return {
        "match_id": inventory.match_id,
        "available_seats": available,
        "unit_price": float(inventory.unit_price),
        "currency": inventory.currency,
        "can_reserve": available > 0,
    }


def booking_event_payload(booking: models.Booking) -> dict:
    return {
        "id": booking.id,
        "match_id": booking.match_id,
        "customer_email": booking.customer_email,
        "quantity": booking.quantity,
        "status": booking.status,
        "total_price": float(booking.total_price),
        "currency": booking.currency,
        "payment_reference": booking.payment_reference,
        "reserved_at": booking.reserved_at.isoformat() if booking.reserved_at else None,
        "expires_at": booking.expires_at.isoformat() if booking.expires_at else None,
    }


def flatten_validation_errors(errors: list[dict]) -> str:
    parts = []
    for err in errors:
        loc = ".".join(str(item) for item in err.get("loc", []))
        msg = err.get("msg", "")
        if loc:
            parts.append(f"{loc}: {msg}")
        else:
            parts.append(msg)
    return "; ".join(parts) if parts else "Некорректные данные запроса"


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return error_response(
        400,
        "Некорректные данные запроса",
        details=flatten_validation_errors(exc.errors()),
    )


@app.get(
    "/bookings",
    summary="Список бронирований",
    description="Возвращает массив бронирований билетов.",
    response_model=list[schemas.BookingOut],
    responses={400: {"model": schemas.ErrorOut}},
)
async def list_bookings(
    matchId: str | None = Query(default=None, description="Фильтр по идентификатору матча."),
    status: str | None = Query(default=None, description="Фильтр по статусу бронирования."),
    email: str | None = Query(default=None, description="Фильтр по email клиента."),
    db: AsyncSession = Depends(get_db),
):
    query = select(models.Booking).order_by(models.Booking.reserved_at.desc())

    if matchId is not None:
        try:
            match_id = parse_int(matchId, "matchId")
        except ValueError as exc:
            return error_response(400, "Некорректные данные запроса", str(exc))
        query = query.where(models.Booking.match_id == match_id)

    if status:
        allowed = {item.value for item in schemas.BookingStatus}
        if status not in allowed:
            return error_response(400, "Некорректные данные запроса", "Неизвестный статус")
        query = query.where(models.Booking.status == status)

    if email:
        query = query.where(models.Booking.customer_email == email)

    result = await db.execute(query)
    bookings = result.scalars().all()
    return [booking_to_out(booking) for booking in bookings]


@app.post(
    "/bookings",
    summary="Создать бронирование",
    description="Создаёт бронирование билетов на матч.",
    response_model=schemas.BookingOut,
    status_code=201,
    responses={
        400: {"model": schemas.ErrorOut},
        409: {"model": schemas.ErrorOut},
    },
)
async def create_booking(payload: schemas.BookingCreate, db: AsyncSession = Depends(get_db)):
    inventory_result = await db.execute(
        select(models.MatchInventory).where(models.MatchInventory.match_id == payload.match_id)
    )
    inventory = inventory_result.scalar_one_or_none()
    if not inventory:
        return error_response(400, "Некорректные данные запроса", "match_id не найден")

    available = max(inventory.capacity - inventory.reserved, 0)
    if payload.quantity > available:
        details = f"Запрошено {payload.quantity}, доступно {available}"
        return error_response(409, "Недостаточно доступных мест", details)

    unit_price = Decimal(str(inventory.unit_price))
    total_price = unit_price * Decimal(str(payload.quantity))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

    booking = models.Booking(
        match_id=payload.match_id,
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
        quantity=payload.quantity,
        unit_price=unit_price,
        total_price=total_price,
        currency=inventory.currency,
        status=schemas.BookingStatus.pending_payment.value,
        expires_at=expires_at,
    )

    inventory.reserved = inventory.reserved + payload.quantity
    db.add(booking)
    await db.commit()
    await db.refresh(booking)

    await broker.publish("booking.created", booking_event_payload(booking))

    payment = await create_payment(
        order_id=booking.id,
        amount=booking.total_price,
        currency=booking.currency,
        description=f"Билеты на матч {booking.match_id}",
        customer_email=booking.customer_email,
    )

    payment_url: str | None = None
    if payment:
        payment_id = payment.get("payment_id")
        payment_url = payment.get("payment_url")
        if payment_id:
            booking.payment_reference = payment_id
            await db.commit()
            await db.refresh(booking)

    if not payment_url:
        payment_url = f"http://localhost:8000/payments/{payment_id}" if payment and payment.get("payment_id") else None

    return booking_to_out(booking, payment_url)


@app.get(
    "/bookings/{bookingId}",
    summary="Получить бронирование по ID",
    response_model=schemas.BookingOut,
    responses={404: {"model": schemas.ErrorOut}},
)
async def get_booking(bookingId: str, db: AsyncSession = Depends(get_db)):
    try:
        booking_id = parse_int(bookingId, "bookingId")
    except ValueError as exc:
        return error_response(400, "Некорректные данные запроса", str(exc))

    booking_result = await db.execute(select(models.Booking).where(models.Booking.id == booking_id))
    booking = booking_result.scalar_one_or_none()
    if not booking:
        return error_response(404, "Ресурс не найден", "Бронирование не найдено")
    return booking_to_out(booking)


@app.delete(
    "/bookings/{bookingId}",
    summary="Отменить бронирование",
    response_model=schemas.BookingOut,
    responses={404: {"model": schemas.ErrorOut}},
)
async def cancel_booking(bookingId: str, db: AsyncSession = Depends(get_db)):
    try:
        booking_id = parse_int(bookingId, "bookingId")
    except ValueError as exc:
        return error_response(400, "Некорректные данные запроса", str(exc))

    booking_result = await db.execute(select(models.Booking).where(models.Booking.id == booking_id))
    booking = booking_result.scalar_one_or_none()
    if not booking:
        return error_response(404, "Ресурс не найден", "Бронирование не найдено")

    if booking.status not in [
        schemas.BookingStatus.cancelled.value,
        schemas.BookingStatus.expired.value,
    ]:
        inventory_result = await db.execute(
            select(models.MatchInventory).where(models.MatchInventory.match_id == booking.match_id)
        )
        inventory = inventory_result.scalar_one_or_none()
        if inventory:
            inventory.reserved = max(inventory.reserved - booking.quantity, 0)
        booking.status = schemas.BookingStatus.cancelled.value
        await db.commit()
        await db.refresh(booking)
        await broker.publish("booking.cancelled", booking_event_payload(booking))

    return booking_to_out(booking)


@app.post(
    "/bookings/{bookingId}/confirm",
    summary="Подтвердить бронирование",
    description="Подтверждает бронирование после внешней оплаты.",
    response_model=schemas.BookingOut,
    responses={400: {"model": schemas.ErrorOut}, 404: {"model": schemas.ErrorOut}},
)
async def confirm_booking(
    bookingId: str,
    payload: schemas.BookingConfirm | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        booking_id = parse_int(bookingId, "bookingId")
    except ValueError as exc:
        return error_response(400, "Некорректные данные запроса", str(exc))

    booking_result = await db.execute(select(models.Booking).where(models.Booking.id == booking_id))
    booking = booking_result.scalar_one_or_none()
    if not booking:
        return error_response(404, "Ресурс не найден", "Бронирование не найдено")

    if booking.status in [
        schemas.BookingStatus.cancelled.value,
        schemas.BookingStatus.expired.value,
    ]:
        return error_response(400, "Некорректные данные запроса", "Бронирование не активно")

    if booking.status != schemas.BookingStatus.confirmed.value:
        booking.status = schemas.BookingStatus.confirmed.value
        if payload and payload.payment_reference:
            booking.payment_reference = payload.payment_reference
        await db.commit()
        await db.refresh(booking)
        await broker.publish("booking.confirmed", booking_event_payload(booking))

    return booking_to_out(booking)


@app.get(
    "/matches/{matchId}/availability",
    summary="Проверить доступность билетов",
    response_model=schemas.AvailabilityOut,
    responses={404: {"model": schemas.ErrorOut}},
)
async def match_availability(matchId: str, db: AsyncSession = Depends(get_db)):
    try:
        match_id = parse_int(matchId, "matchId")
    except ValueError as exc:
        return error_response(400, "Некорректные данные запроса", str(exc))

    inventory_result = await db.execute(
        select(models.MatchInventory).where(models.MatchInventory.match_id == match_id)
    )
    inventory = inventory_result.scalar_one_or_none()
    if not inventory:
        return error_response(404, "Ресурс не найден", "Матч не найден")
    return availability_to_out(inventory)
