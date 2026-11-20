"""Belgeye bağlı yenileme dönemleri; eski dönemler korunur."""

import uuid
from datetime import date, datetime

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
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DocumentRenewal(Base):
    __tablename__ = "document_renewals"
    __table_args__ = (
        CheckConstraint("kind IN ('police','sozlesme')", name="ck_renewals_kind"),
        CheckConstraint("warning_days BETWEEN 1 AND 365", name="ck_renewals_warning"),
        CheckConstraint(
            "expires_on IS NULL OR starts_on IS NULL OR expires_on >= starts_on",
            name="ck_renewals_dates",
        ),
        Index(
            "uq_renewals_open_document",
            "document_id",
            unique=True,
            postgresql_where=text("is_closed = false"),
            sqlite_where=text("is_closed = 0"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doc_documents.id", ondelete="CASCADE"), index=True
    )
    previous_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_renewals.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    kind: Mapped[str] = mapped_column(String(20))
    reference_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    starts_on: Mapped[date | None] = mapped_column(Date(), nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date(), nullable=True, index=True)
    warning_days: Mapped[int] = mapped_column(Integer(), default=30)
    annual: Mapped[bool] = mapped_column(Boolean(), default=True)
    responsible_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean(), default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
