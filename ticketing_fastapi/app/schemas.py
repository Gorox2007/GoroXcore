from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class BookingStatus(str, Enum):
    pending_payment = "pending_payment"
    confirmed = "confirmed"
    cancelled = "cancelled"
    expired = "expired"


class BookingCreate(BaseModel):
    match_id: int = Field(..., description="ID матча", examples=[101])
    customer_name: str = Field(..., description="ФИО клиента", max_length=255)
    customer_email: EmailStr = Field(..., description="Email клиента", examples=["fan@example.com"])
    quantity: int = Field(..., description="Количество билетов", ge=1, examples=[2])


class BookingConfirm(BaseModel):
    payment_reference: str | None = Field(
        default=None,
        description="Идентификатор внешнего платежа",
        max_length=255,
        examples=["pay_abc123"],
    )


class BookingOut(BaseModel):
    id: int = Field(..., description="Уникальный идентификатор бронирования")
    match_id: int = Field(..., description="ID матча")
    customer_name: str = Field(..., description="ФИО клиента")
    customer_email: EmailStr = Field(..., description="Email клиента")
    quantity: int = Field(..., description="Количество билетов")
    unit_price: float = Field(..., description="Цена за билет")
    total_price: float = Field(..., description="Итоговая стоимость всех билетов")
    currency: str = Field(..., description="Код валюты ISO")
    status: BookingStatus = Field(..., description="Текущий статус бронирования")
    reserved_at: datetime = Field(..., description="Время создания бронирования")
    expires_at: datetime = Field(..., description="Время истечения бронирования")
    payment_reference: str | None = Field(
        default=None, description="Идентификатор внешнего платежа"
    )


class AvailabilityOut(BaseModel):
    match_id: int = Field(..., description="ID матча")
    available_seats: int = Field(..., description="Количество доступных мест")
    unit_price: float = Field(..., description="Цена за билет")
    currency: str = Field(..., description="Код валюты ISO")
    can_reserve: bool = Field(..., description="Можно ли создать бронирование")


class ErrorOut(BaseModel):
    error: str = Field(..., description="Описание ошибки")
    code: int = Field(..., description="HTTP-код ошибки")
    details: str | None = Field(default=None, description="Детали ошибки")
