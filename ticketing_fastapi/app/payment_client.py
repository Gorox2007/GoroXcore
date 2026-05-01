import logging
import os
from decimal import Decimal

import httpx

logger = logging.getLogger(__name__)

PAYMENT_SERVICE_URL = os.getenv(
    "PAYMENT_SERVICE_URL", "http://payment-service:8000"
)


async def create_payment(
    order_id: int,
    amount: Decimal,
    currency: str,
    description: str,
    customer_email: str,
) -> dict | None:
    success_url = os.getenv("PAYMENT_SUCCESS_URL", "http://localhost:8001/bookings/success")
    fail_url = os.getenv("PAYMENT_FAIL_URL", "http://localhost:8001/bookings/fail")
    webhook_url = os.getenv("PAYMENT_WEBHOOK_URL", "http://ticketing-fastapi:8001/webhook")

    payload = {
        "order_id": order_id,
        "amount": float(amount),
        "currency": currency,
        "description": description,
        "customer_email": customer_email,
        "success_url": success_url,
        "fail_url": fail_url,
        "webhook_url": webhook_url,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{PAYMENT_SERVICE_URL}/payments",
                json=payload,
            )
        if resp.is_success:
            data = resp.json()
            logger.info("Payment created: %s for order %s", data.get("payment_id"), order_id)
            return data
        else:
            logger.error(
                "Payment service error: %s %s", resp.status_code, resp.text
            )
            return None
    except Exception as e:
        logger.exception("Failed to call payment service: %s", e)
        return None
