"""PersonGuardian modeli — veli-sporcu ilişkisi."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.club import Club
    from app.models.person import Person


class PersonGuardian(Base):
    """Sporcu-veli bağlantı kaydı.

    Kısıtlamalar:
      - (club_id, athlete_person_id, guardian_person_id) benzersiz
      - athlete_person_id <> guardian_person_id (kişi kendini veli yapamaz)
      - is_primary teklik kuralı application katmanında yönetilir (bir sporcu için
        yalnızca 1 primary veli olabilir; yeni primary atanınca eskisi temizlenir)
    """

    __tablename__ = "person_guardians"
    __table_args__ = (
        UniqueConstraint(
            "club_id",
            "athlete_person_id",
            "guardian_person_id",
            name="uq_person_guardians_club_athlete_guardian",
        ),
        CheckConstraint(
            "athlete_person_id <> guardian_person_id",
            name="ck_person_guardians_no_self_ref",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    athlete_person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), nullable=False
    )
    guardian_person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_pickup: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_receive_notifications: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # İlişkiler — foreign_keys zorunlu: iki FK aynı tabloya işaret ediyor
    athlete: Mapped["Person"] = relationship(
        foreign_keys=[athlete_person_id],
        back_populates="athlete_guardian_links",
    )
    guardian: Mapped["Person"] = relationship(
        foreign_keys=[guardian_person_id],
        back_populates="guardian_links",
    )
    club: Mapped["Club"] = relationship(foreign_keys=[club_id])

    def __repr__(self) -> str:
        return (
            f"<PersonGuardian athlete={self.athlete_person_id!s:.8} "
            f"guardian={self.guardian_person_id!s:.8} primary={self.is_primary}>"
        )
