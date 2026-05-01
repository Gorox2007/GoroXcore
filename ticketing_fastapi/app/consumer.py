import asyncio
import json
import logging

from aio_pika.abc import AbstractIncomingMessage

from .broker import RabbitMQBroker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

RECONNECT_DELAY_SECONDS = 5


async def handle_message(message: AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        data = json.loads(message.body.decode("utf-8"))
        event_type = data.get("event_type", "unknown")
        payload = data.get("payload", {})
        logger.info(
            "Получено событие '%s' для бронирования id=%s",
            event_type,
            payload.get("id"),
        )


async def run_consumer() -> None:
    local_broker = RabbitMQBroker()
    while True:
        try:
            await local_broker.connect()
            if local_broker.queue is None:
                raise RuntimeError("Очередь RabbitMQ не инициализирована")

            logger.info("Консьюмер слушает очередь '%s'", local_broker.queue_name)
            async with local_broker.queue.iterator() as queue_iter:
                async for message in queue_iter:
                    await handle_message(message)
        except asyncio.CancelledError:
            logger.info("Консьюмер остановлен")
            break
        except Exception:
            logger.exception("Ошибка консьюмера, переподключение через %s сек", RECONNECT_DELAY_SECONDS)
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)
        finally:
            await local_broker.close()


def main() -> None:
    asyncio.run(run_consumer())


if __name__ == "__main__":
    main()
