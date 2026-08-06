"""Üye numarası sıra sayacı — yarış koşuluna dayanıklı."""
import uuid
from sqlalchemy import ForeignKey, Integer, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class MemberCounter(Base):
    __tablename__ = "member_counters"

    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    year: Mapped[int] = mapped_column(SmallInteger(), nullable=False, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
