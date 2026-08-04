"""MembershipApplication modeli — üyelik başvurusu ve imza süreci."""
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base

if TYPE_CHECKING:
    from app.models.club import Club
    from app.models.person import Person
    from app.models.sports_branch import SportsBranch

# ── Geçerli durum kodları ve geçiş matrisi ───────────────────────────────────

VALID_STATUSES = {"draft", "submitted", "approved", "rejected", "cancelled"}

# Hangi durumdan hangi duruma geçilebilir
# (from_status) -> {allowed_to_statuses}
STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft":     {"submitted", "cancelled"},
    "submitted": {"approved", "rejected", "cancelled"},
    "rejected":  {"draft"},          # yeniden başvuru
    "approved":  set(),              # terminal
    "cancelled": set(),              # terminal
}

# Onay gerektiren geçişler — yalnızca kisi:approve rolü yapabilir
APPROVE_REQUIRED_TRANSITIONS = {("submitted", "approved"), ("submitted", "rejected")}

# Soft delete yapılamayacak durumlar
NO_DELETE_STATUSES = {"approved", "rejected"}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    return to_status in STATUS_TRANSITIONS.get(from_status, set())


def requires_approval(from_status: str, to_status: str) -> bool:
    return (from_status, to_status) in APPROVE_REQUIRED_TRANSITIONS


class MembershipApplication(Base):
    __tablename__ = "membership_applications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # person_id nullable: başvuru kişi kaydı olmadan da oluşturulabilir
    person_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"), nullable=True, index=True
    )

    application_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # Başvuru sahibi bilgileri (person kaydından bağımsız kopyalanır)
    applicant_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # backward compat
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    national_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    birth_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    blood_type: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)

    sports_branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("sports_branches.id", ondelete="SET NULL"), nullable=True
    )

    guardian_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    guardian_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    consent_text_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    consent_accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")

    # JSONB PostgreSQL'de, JSON SQLite testlerinde
    form_data: Mapped[Optional[Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )

    # PDF
    pdf_object_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pdf_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    pdf_generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # İmza
    signature_object_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    signature_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    signed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    signed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Onay / ret
    approved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)

    # İptal
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)

    # Zaman damgaları
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # İlişkiler
    club: Mapped["Club"] = relationship(back_populates="membership_applications")
    person: Mapped[Optional["Person"]] = relationship(back_populates="membership_applications")
    branch: Mapped[Optional["SportsBranch"]] = relationship(foreign_keys=[sports_branch_id])

    def __repr__(self) -> str:
        return f"<MembershipApplication {self.application_number} [{self.status}]>"
