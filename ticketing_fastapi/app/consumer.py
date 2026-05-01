import asyncio
import json
import logging
import os

from aio_pika import ExchangeType, connect_robust
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from .database import ASYNC_DATABASE_URL, engine
from .models import Booking
from .schemas import BookingStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

RECONNECT_DELAY_SECONDS = 5

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def handle_ticketing_event(data: dict) -> None:
    event_type = data.get("event_type", "unknown")
    payload = data.get("payload", {})
    logger.info("Ticketing event: %s booking id=%s", event_type, payload.get("id"))


async def handle_payment_event(data: dict) -> None:
    event_status = data.get("status")
    order_id = data.get("order_id")
    payment_id = data.get("payment_id")
    logger.info("Payment event: %s for order %s (payment %s)", event_status, order_id, payment_id)

    if event_status != "paid" or order_id is None:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Booking).where(Booking.id == order_id))
        booking = result.scalar_one_or_none()
        if not booking:
            logger.warning("Booking %s not found for payment event", order_id)
            return

        if booking.status in (BookingStatus.cancelled.value, BookingStatus.expired.value):
            logger.warning("Booking %s is %s, skipping confirm", order_id, booking.status)
            return

        if booking.status != BookingStatus.confirmed.value:
            booking.status = BookingStatus.confirmed.value
            if payment_id:
                booking.payment_reference = payment_id
            await db.commit()
            logger.info("Booking %s confirmed after payment", order_id)


async def on_message(message: AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        data = json.loads(message.body.decode("utf-8"))
        if "event_type" in data:
            await handle_ticketing_event(data)
        else:
            await handle_payment_event(data)


async def run_consumer() -> None:
    rmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    while True:
        try:
            connection = await connect_robust(rmq_url)
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=1)

            ticketing_queue = await channel.declare_queue("ticketing.events", durable=True)

            payments_exchange = await channel.declare_exchange(
                "payments", ExchangeType.TOPIC, durable=True
            )
            payment_queue = await channel.declare_queue("payment_events", durable=True)
            await payment_queue.bind(payments_exchange, routing_key="payment.*")

            logger.info(
                "Consumer listening: ticketing.events + payments exchange (payment.*)"
            )

            await ticketing_queue.consume(on_message)
            await payment_queue.consume(on_message)

            await asyncio.Future()
        except asyncio.CancelledError:
            logger.info("Consumer stopped")
            break
        except Exception:
            logger.exception(
                "Consumer error, reconnecting in %ss", RECONNECT_DELAY_SECONDS
            )
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)
        finally:
            if not connection.is_closed:
                await connection.close()


def main() -> None:
    asyncio.run(run_consumer())


if __name__ == "__main__":
    main()
