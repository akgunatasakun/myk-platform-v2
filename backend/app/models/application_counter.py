"""ApplicationCounter — yarış koşuluna dayanıklı başvuru numarası üretimi.

Numara formatı: MYK-{YYYY}-{N:06d}
Örnek: MYK-2026-000001

Upsert stratejisi (atomic):
    INSERT INTO application_counters (club_id, year, last_number)
    VALUES (:club_id, :year, 1)
    ON CONFLICT (club_id, year)
    DO UPDATE SET last_number = application_counters.last_number + 1
    RETURNING last_number

PostgreSQL ve SQLite 3.24+ üzerinde çalışır.
"""
import uuid

from sqlalchemy import ForeignKey, Integer, PrimaryKeyConstraint, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApplicationCounter(Base):
    __tablename__ = "application_counters"
    __table_args__ = (
        PrimaryKeyConstraint("club_id", "year", name="pk_application_counters"),
    )

    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<ApplicationCounter club={self.club_id} year={self.year} last={self.last_number}>"
