"""NotificationDelivery — alıcı bazlı gönderim kaydı (Sprint 15B).

Yaşam döngüsü:
  pending   → gönderim bekliyor (attempt_count < MAX ya da yeni oluşturuldu)
  done      → başarıyla gönderildi (sent_at set)
  failed    → max deneme aşıldı veya kalıcı hata (last_error dolu)

Event completion kuralı:
  Bir DomainEvent'e ait tüm delivery'ler terminal (done/failed) olunca
  event.status = 'done' yapılır. Bu, dispatch_pending_events içinde
  toplu olarak kontrol edilir.

Unique constraint:
  (event_id, recipient_email, channel) — aynı event için aynı alıcıya
  aynı kanaldan iki kez kayıt açılmaz; idempotent dispatch sağlar.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.events import DomainEvent
    from app.models.person import Person


DELIVERY_STATUSES = ("pending", "done", "failed")
DELIVERY_CHANNELS = ("email", "push")  # push: Sprint 15C


class NotificationDelivery(Base):
    """Alıcı + kanal bazlı gönderim kaydı."""

    __tablename__ = "notification_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("domain_events.id", ondelete="CASCADE"), nullable=False
    )
    # NULL → kulüp genel e-postası gibi person'a bağlı olmayan alıcı
    recipient_person_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"), nullable=True
    )
    recipient_email: Mapped[str] = mapped_column(Text(), nullable=False)
    channel: Mapped[str] = mapped_column(Text(), nullable=False, default="email")

    # ── Durum ─────────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(Text(), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default="0"
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Concurrent claiming (Sprint 15B) ──────────────────────────────────────
    # Worker, gönderimi denemeden önce bu iki alanı atomik UPDATE ile doldurur.
    # İşlem bitince her ikisi de NULL'a döner.
    # Crash recovery: processing_since + 10dk geçmişse delivery tekrar serbest.
    claimed_worker_id: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    processing_since: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── İlişkiler ─────────────────────────────────────────────────────────────
    event: Mapped["DomainEvent"] = relationship(
        foreign_keys=[event_id],
        lazy="select",
    )
    recipient: Mapped[Optional["Person"]] = relationship(
        foreign_keys=[recipient_person_id],
        lazy="select",
    )

    @property
    def is_terminal(self) -> bool:
        return self.status in ("done", "failed")

    def __repr__(self) -> str:
        return (
            f"<NotificationDelivery event={self.event_id!s:.8} "
            f"to={self.recipient_email!r} ch={self.channel} st={self.status!r}>"
        )
