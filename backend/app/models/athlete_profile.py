"""AthleteProfile modeli — persons tablosunun 1:1 sporcu uzantısı."""
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.sports_branch import SportsBranch


class AthleteProfile(Base):
    __tablename__ = "athlete_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Branş & sportif sınıf
    sports_branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("sports_branches.id", ondelete="SET NULL"), nullable=True
    )
    class_name: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    level: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, default="baslangic"
    )

    # Lisans / vize
    license_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    license_expiry_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    visa_expiry_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)

    # Sağlık
    health_report_expiry_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    swimming_qualified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Tıbbi / özel durum (rol bazlı maskelenir)
    allergies: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    special_conditions: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)

    # KVKK & izinler
    kvkk_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    kvkk_consent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    kvkk_text_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    photo_video_consent: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # İlişkiler
    person: Mapped["Person"] = relationship(back_populates="athlete_profile")
    sports_branch: Mapped[Optional["SportsBranch"]] = relationship(lazy="selectin")

    def __repr__(self) -> str:
        return f"<AthleteProfile person_id={self.person_id}>"
