"""Kulüp içi, rol hedefli duyurular."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Announcement(Base):
    __tablename__ = "announcements"
    __table_args__ = (
        CheckConstraint(
            "status IN ('taslak','yayinda','arsiv')", name="ck_announcements_status"
        ),
        CheckConstraint(
            "ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on",
            name="ck_announcements_dates",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(20), default="taslak")
    important: Mapped[bool] = mapped_column(Boolean(), default=False)
    starts_on: Mapped[date | None] = mapped_column(Date(), nullable=True)
    ends_on: Mapped[date | None] = mapped_column(Date(), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean(), default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    audiences: Mapped[list["AnnouncementAudience"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class AnnouncementAudience(Base):
    __tablename__ = "announcement_audiences"
    announcement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"), primary_key=True
    )
    role_code: Mapped[str] = mapped_column(String(50), primary_key=True)
