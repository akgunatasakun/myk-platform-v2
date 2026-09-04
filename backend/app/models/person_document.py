"""Veli portalındaki kişisel evrakların ORM modelleri."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


DOCUMENT_TYPES = (
    "profile_photo",
    "identity_copy",
    "health_report",
    "parental_permission",
    "undertaking",
    "waiver",
    "other",
)
REVIEW_STATUSES = ("pending", "approved", "rejected", "expired", "superseded")
SCAN_STATUSES = ("pending", "clean", "infected", "failed", "skipped_dev")


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _sensitive_default(context: object) -> bool:
    """Sağlık raporunu ORM insertlerinde varsayılan olarak hassas işaretle."""
    parameters = context.get_current_parameters()  # type: ignore[attr-defined]
    return parameters.get("document_type") == "health_report"


class PersonDocument(Base):
    __tablename__ = "person_documents"
    __table_args__ = (
        CheckConstraint(
            f"document_type IN ({_sql_values(DOCUMENT_TYPES)})",
            name="ck_person_documents_document_type",
        ),
        CheckConstraint(
            f"review_status IN ({_sql_values(REVIEW_STATUSES)})",
            name="ck_person_documents_review_status",
        ),
        CheckConstraint(
            f"scan_status IN ({_sql_values(SCAN_STATUSES)})",
            name="ck_person_documents_scan_status",
        ),
        CheckConstraint(
            "document_type <> 'health_report' OR is_sensitive IS TRUE",
            name="ck_person_documents_health_sensitive",
        ),
        Index(
            "ix_person_documents_club_subject_deleted",
            "club_id",
            "subject_person_id",
            "is_deleted",
        ),
        Index(
            "ix_person_documents_club_type_scan",
            "club_id",
            "document_type",
            "scan_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
    )
    subject_person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    guardian_link_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("person_guardians.id", ondelete="SET NULL"), nullable=True
    )
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_key: Mapped[str] = mapped_column(
        String(1024), nullable=False, unique=True
    )
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    retain_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    scan_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    is_sensitive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=_sensitive_default
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    supersedes_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("person_documents.id", ondelete="SET NULL"), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_basis: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )

    representatives: Mapped[list["PersonDocumentRepresentative"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    supersedes: Mapped[Optional["PersonDocument"]] = relationship(
        remote_side=[id], foreign_keys=[supersedes_id]
    )


class PersonDocumentRepresentative(Base):
    __tablename__ = "person_document_representatives"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "person_id",
            "representative_role",
            name="uq_person_document_representative_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("person_documents.id", ondelete="CASCADE"), nullable=False
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), nullable=False
    )
    guardian_link_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("person_guardians.id", ondelete="SET NULL"), nullable=True
    )
    representative_role: Mapped[str] = mapped_column(String(64), nullable=False)
    signed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    document: Mapped[PersonDocument] = relationship(back_populates="representatives")
