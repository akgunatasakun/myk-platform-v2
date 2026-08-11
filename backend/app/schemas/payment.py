"""Payment (Ödeme/Tahsilat) Pydantic şemaları — Pydantic v2.

Tüm input şemaları extra="forbid" kullanır.
Status değerleri: pending | paid (Flask: beklemede | odendi)
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

PAYMENT_STATUS_VALUES = ["pending", "paid"]


# ── PaymentCreate ─────────────────────────────────────────────────────────────

class PaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: Optional[uuid.UUID] = None
    amount: Decimal = Field(..., gt=0, description="Tutar, 0'dan büyük olmalı")
    payment_type: Optional[str] = None
    payment_method: Optional[str] = None
    due_date: Optional[date] = None
    paid_at: Optional[date] = None
    status: Literal["pending", "paid"] = "pending"
    receipt_no: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Tutar 0'dan büyük olmalıdır.")
        return v


# ── PaymentUpdate ─────────────────────────────────────────────────────────────

class PaymentUpdate(BaseModel):
    """Yalnızca güncellenebilen alanlar — Flask PUT davranışı."""
    model_config = ConfigDict(extra="forbid")

    status: Optional[Literal["pending", "paid"]] = None
    paid_at: Optional[date] = None
    payment_method: Optional[str] = None
    receipt_no: Optional[str] = None
    notes: Optional[str] = None


# ── PaymentOut ────────────────────────────────────────────────────────────────

class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    club_id: uuid.UUID
    recorded_by_user_id: Optional[uuid.UUID] = None
    person_id: Optional[uuid.UUID] = None
    person_name: Optional[str] = None           # computed — router'da doldurulur
    amount: Decimal
    payment_type: Optional[str] = None
    payment_method: Optional[str] = None
    due_date: Optional[date] = None
    paid_at: Optional[date] = None
    status: str
    receipt_no: Optional[str] = None
    notes: Optional[str] = None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class PaymentListOut(BaseModel):
    items: List[PaymentOut]
    total: int
    skip: int
    limit: int


# ── OverduePaymentOut ─────────────────────────────────────────────────────────

class OverduePaymentOut(PaymentOut):
    """Gecikmiş ödeme — gecikme_gun ek alanı."""
    gecikme_gun: int = 0


# ── Revenue Report ────────────────────────────────────────────────────────────

class RevenueByMonth(BaseModel):
    """Aylık gelir özeti — Flask gelir_rapor() karşılığı."""
    ay: str                             # YYYY-MM formatında
    payment_type: Optional[str] = None
    toplam: Decimal
    adet: int


class RevenueReport(BaseModel):
    items: List[RevenueByMonth]
    toplam_gelir: Decimal               # tüm dönem toplamı
