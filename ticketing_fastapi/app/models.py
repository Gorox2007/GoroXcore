from sqlalchemy import CheckConstraint, Column, DateTime, Integer, Numeric, String
from sqlalchemy.sql import func

from .database import Base


class MatchInventory(Base):
    __tablename__ = "match_inventories"

    match_id = Column(Integer, primary_key=True, index=True)
    capacity = Column(Integer, nullable=False)
    reserved = Column(Integer, nullable=False, default=0, server_default="0")
    unit_price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="RUB", server_default="RUB")
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("reserved <= capacity", name="reserved_not_exceed_capacity"),
    )


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, index=True, nullable=False)
    customer_name = Column(String(255), nullable=False)
    customer_email = Column(String(255), index=True, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="RUB", server_default="RUB")
    status = Column(
        String(20),
        index=True,
        nullable=False,
        default="pending_payment",
        server_default="pending_payment",
    )
    reserved_at = Column(DateTime, nullable=False, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    payment_reference = Column(String(255), nullable=True)
