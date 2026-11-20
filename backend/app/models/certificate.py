"""Kulüp eğitim sertifikası kayıtları; resmî kurum entegrasyonu içermez."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TrainingCertificate(Base):
    __tablename__ = "training_certificates"
    __table_args__ = (
        UniqueConstraint("club_id", "number", name="uq_certificates_club_number"),
        CheckConstraint(
            "status IN ('draft', 'issued', 'revoked')", name="ck_certificates_status"
        ),
        CheckConstraint(
            "status = 'draft' OR (number IS NOT NULL AND issued_on IS NOT NULL)",
            name="ck_certificates_issued_fields",
        ),
        CheckConstraint(
            "expires_on IS NULL OR issued_on IS NULL OR expires_on >= issued_on",
            name="ck_certificates_dates",
        ),
        Index(
            "uq_certificates_live_enrollment",
            "club_id",
            "enrollment_id",
            unique=True,
            postgresql_where=text(
                "is_deleted = false AND status IN ('draft', 'issued')"
            ),
            sqlite_where=text("is_deleted = 0 AND status IN ('draft', 'issued')"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), index=True
    )
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("training_enrollments.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(240))
    person_name: Mapped[str] = mapped_column(String(300))
    course_name: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    issued_on: Mapped[date | None] = mapped_column(Date(), nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date(), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    issued_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean(), default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
