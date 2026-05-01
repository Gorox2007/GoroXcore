import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from . import models
from .database import sync_engine

SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


def seed(clear: bool = False) -> None:
    db = SyncSessionLocal()
    try:
        if clear:
            db.query(models.Booking).delete()
            db.query(models.MatchInventory).delete()
            db.commit()

        inventories = [
            {"match_id": 101, "capacity": 500, "unit_price": Decimal("1500.00")},
            {"match_id": 102, "capacity": 320, "unit_price": Decimal("1200.00")},
            {"match_id": 103, "capacity": 800, "unit_price": Decimal("2000.00")},
        ]

        for item in inventories:
            inventory = (
                db.query(models.MatchInventory)
                .filter(models.MatchInventory.match_id == item["match_id"])
                .first()
            )
            if inventory:
                inventory.capacity = item["capacity"]
                inventory.unit_price = item["unit_price"]
                inventory.currency = "RUB"
            else:
                db.add(
                    models.MatchInventory(
                        match_id=item["match_id"],
                        capacity=item["capacity"],
                        reserved=0,
                        unit_price=item["unit_price"],
                        currency="RUB",
                    )
                )

        db.commit()

        now = datetime.now(timezone.utc)
        bookings = [
            {
                "match_id": 101,
                "customer_name": "Ivan Petrov",
                "customer_email": "ivan.petrov@example.com",
                "quantity": 2,
                "status": "pending_payment",
                "expires_at": now + timedelta(minutes=30),
            },
            {
                "match_id": 101,
                "customer_name": "Anna Smirnova",
                "customer_email": "anna.smirnova@example.com",
                "quantity": 1,
                "status": "confirmed",
                "expires_at": now + timedelta(minutes=30),
                "payment_reference": "pay_demo_101",
            },
            {
                "match_id": 102,
                "customer_name": "Oleg Ivanov",
                "customer_email": "oleg.ivanov@example.com",
                "quantity": 4,
                "status": "confirmed",
                "expires_at": now + timedelta(minutes=30),
                "payment_reference": "pay_demo_102",
            },
            {
                "match_id": 103,
                "customer_name": "Maria Sokolova",
                "customer_email": "maria.sokolova@example.com",
                "quantity": 3,
                "status": "cancelled",
                "expires_at": now + timedelta(minutes=30),
            },
            {
                "match_id": 103,
                "customer_name": "Sergey Kuznetsov",
                "customer_email": "sergey.k@example.com",
                "quantity": 5,
                "status": "expired",
                "expires_at": now - timedelta(minutes=10),
            },
        ]

        for data in bookings:
            inventory = (
                db.query(models.MatchInventory)
                .filter(models.MatchInventory.match_id == data["match_id"])
                .first()
            )
            if not inventory:
                continue

            unit_price = Decimal(str(inventory.unit_price))
            total_price = unit_price * Decimal(str(data["quantity"]))
            db.add(
                models.Booking(
                    match_id=data["match_id"],
                    customer_name=data["customer_name"],
                    customer_email=data["customer_email"],
                    quantity=data["quantity"],
                    unit_price=unit_price,
                    total_price=total_price,
                    currency=inventory.currency,
                    status=data["status"],
                    expires_at=data["expires_at"],
                    payment_reference=data.get("payment_reference"),
                )
            )

        db.commit()

        reserved_by_match = {}
        active_statuses = {"pending_payment", "confirmed"}
        for booking in db.execute(
            select(models.Booking).where(models.Booking.status.in_(active_statuses))
        ).scalars():
            reserved_by_match[booking.match_id] = (
                reserved_by_match.get(booking.match_id, 0) + booking.quantity
            )

        for inventory in db.execute(select(models.MatchInventory)).scalars():
            inventory.reserved = min(
                inventory.capacity, reserved_by_match.get(inventory.match_id, 0)
            )

        db.commit()
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Seed ticketing database with data.")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete existing bookings and inventory before seeding.",
    )
    args = parser.parse_args()
    seed(clear=args.clear)


if __name__ == "__main__":
    main()
