"""Kulüp (tenant) modeli."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import JSON, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.sports_branch import SportsBranch
    from app.models.membership_application import MembershipApplication


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    plan: Mapped[str] = mapped_column(String(20), default="starter")  # starter | pro | enterprise
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    branches: Mapped[List["SportsBranch"]] = relationship(
        back_populates="club",
        cascade="all, delete-orphan",
    )
    membership_applications: Mapped[List["MembershipApplication"]] = relationship(
        back_populates="club",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Club {self.slug}>"
