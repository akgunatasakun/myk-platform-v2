"""DomainEvent modeli — platform geneli event/bildirim kaydı.

Tasarım:
  - status yaşam döngüsü: pending → processing → done | failed
  - acknowledged_at: kulüp yönetim feed'inde okundu işareti (kulüp seviyesi).
    Gelecekte birden fazla kullanıcı okuma durumu gerekirse ayrı tablo eklenir.
  - scheduled_for: nightly scan olayları için üretim tarihi (UTC),
    anlık olaylar için oluşturma zamanı.
  - Unique constraint mantığı: migration 0012'deki partial index üzerinden
    (club_id, event_type, aggregate_id, date(scheduled_for)) → günde bir kez.

Event type adlandırma standardı: '<aggregate>.<action>'
  'payment.overdue'
  'payment.created'
  'athlete.license.expiring_soon'
  'athlete.visa.expiring_soon'
  'athlete.health_report.expiring_soon'
  'equipment.maintenance.due'
  'equipment.insurance.expiring_soon'
  'training.session.created'
  'training.session.starts_tomorrow'
  'application.submitted'
  'application.approved'
  'application.rejected'
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


DOMAIN_EVENT_STATUSES = ("pending", "processing", "done", "failed")


class DomainEvent(Base):
    """Platform geneli event/bildirim kaydı."""

    __tablename__ = "domain_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(Text(), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(Text(), nullable=False)
    aggregate_id: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON(), nullable=True)
    status: Mapped[str] = mapped_column(Text(), nullable=False, default="pending")

    # Nightly scan olayları: o günkü UTC midnight. Anlık: oluşturma zamanı.
    # Unique index (club_id, event_type, aggregate_id, date(scheduled_for)) üzerinden
    # aynı aggregate için günde bir kez üretilmesini garanti eder.
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Kulüp seviyesinde "okundu" işareti
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Retry alanları (migration 0014) ──────────────────────────────────────
    # attempt_count : kaç kez denendi (0 = henüz denenmedi)
    # last_error    : en son hata mesajı
    # next_attempt_at: bir sonraki deneme zamanı (NULL = hemen uygun)
    attempt_count: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default="0"
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<DomainEvent type={self.event_type!r} "
            f"aggregate={self.aggregate_type}/{self.aggregate_id} "
            f"status={self.status!r}>"
        )
