"""Payment (Ödeme/Tahsilat) modeli — gelir ve tahsilat kayıtları."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey,
    Numeric, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.user import User


class Payment(Base):
    """Ödeme/tahsilat kaydı.

    Flask 'odemeler' tablosunun doğrudan karşılığı.

    Tasarım:
      - person_id nullable: kulüp genel tahsilatları için sporcu/üye gerekmeyebilir.
      - payment_type serbest TEXT: enum migration gerektirmeden genişletilebilir.
      - status: 'pending' | 'paid' — uygulama katmanında doğrulanır, DB TEXT.
      - training_enrollments.payment_status bu tabloyla otomatik senkronize değil.
    """

    __tablename__ = "payments"

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recorded_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    person_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_type: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    paid_at: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    status: Mapped[str] = mapped_column(Text(), nullable=False, default="pending")
    receipt_no: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # İlişkiler
    person: Mapped[Optional["Person"]] = relationship(
        foreign_keys=[person_id],
        lazy="select",
    )
    recorded_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[recorded_by_user_id],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<Payment amount={self.amount} status={self.status!r} "
            f"club={self.club_id!s:.8}>"
        )
