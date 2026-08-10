"""Training (Fiziksel Eğitim) veri modelleri — kurs, oturum, kayıt, yoklama.

Domain notu: Bu modeller Academy (online LMS) ile tamamen ayrıdır; aralarında FK yok.
Kimlik prensibi:
  - Katılımcı / eğitmen → persons.id
  - İşlemi yapan kullanıcı → users.id
"""
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Numeric, Text, Time, UniqueConstraint, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.user import User


class TrainingCourse(Base):
    """Fiziksel yelken kursu."""

    __tablename__ = "training_courses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    class_name: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)     # eski: sinif
    level: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)          # eski: seviye
    start_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    schedule_text: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)  # eski: gun_saatleri
    capacity: Mapped[int] = mapped_column(nullable=False, default=0)
    fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    instructor_person_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(Text(), nullable=False, default="planlandi")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    instructor: Mapped[Optional["Person"]] = relationship(
        foreign_keys=[instructor_person_id],
        lazy="select",
    )
    sessions: Mapped[List["TrainingSession"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="TrainingSession.session_date",
    )
    enrollments: Mapped[List["TrainingEnrollment"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )

    @property
    def active_enrollment_count(self) -> int:
        return sum(
            1 for e in self.enrollments
            if e.status == "active" and not e.is_deleted
        )

    def __repr__(self) -> str:
        return f"<TrainingCourse {self.name!r} club={self.club_id!s:.8}>"


class TrainingSession(Base):
    """Ders oturumu — kurs + tarih normalize edilmiş entity.

    Eski yoklama tablosundaki (kurs_id + tarih) bileşik anahtarı replace eder.
    Aynı kurs için aynı gün birden fazla oturum açılabilir (DB-level unique yok).
    """

    __tablename__ = "training_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("training_courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_date: Mapped[date] = mapped_column(Date(), nullable=False)
    start_time: Mapped[Optional[time]] = mapped_column(Time(), nullable=True)
    end_time: Mapped[Optional[time]] = mapped_column(Time(), nullable=True)
    instructor_person_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text(), nullable=False, default="planli")
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    course: Mapped["TrainingCourse"] = relationship(back_populates="sessions")
    instructor: Mapped[Optional["Person"]] = relationship(
        foreign_keys=[instructor_person_id],
        lazy="select",
    )
    attendance: Mapped[List["TrainingAttendance"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<TrainingSession course={self.course_id!s:.8} date={self.session_date}>"


class TrainingEnrollment(Base):
    """Kişi-kurs kaydı.

    Aktif duplicate kontrolü:
      - PostgreSQL: partial unique index (uq_training_enrollments_active) üzerinden
      - Tüm diyalektler: service katmanında explicit kontrol

    payment_status: Sprint 6A'da cache olarak tutulur.
    Sprint 6B'de payments domain devralır; bu alan özet/readonly olabilir.
    """

    __tablename__ = "training_enrollments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("training_courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(Text(), nullable=False, default="active")
    payment_status: Mapped[str] = mapped_column(Text(), nullable=False, default="pending")
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    course: Mapped["TrainingCourse"] = relationship(back_populates="enrollments")
    person: Mapped["Person"] = relationship(
        foreign_keys=[person_id],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<TrainingEnrollment person={self.person_id!s:.8} "
            f"course={self.course_id!s:.8} status={self.status}>"
        )


class TrainingAttendance(Base):
    """Oturum bazlı yoklama kaydı.

    status değerleri (kaynak: Flask GECERLI set):
      var, yok, izinli, gecikti

    Tarih bilgisi training_sessions.session_date üzerinden okunur;
    bu tabloda tekrarlanmaz.
    """

    __tablename__ = "training_attendance"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "person_id",
            name="uq_training_attendance_session_person",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("training_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(Text(), nullable=False, default="var")
    check_in_time: Mapped[Optional[time]] = mapped_column(Time(), nullable=True)   # eski: giris_saati
    check_out_time: Mapped[Optional[time]] = mapped_column(Time(), nullable=True)  # eski: cikis_saati
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    recorded_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    session: Mapped["TrainingSession"] = relationship(back_populates="attendance")
    person: Mapped["Person"] = relationship(
        foreign_keys=[person_id],
        lazy="select",
    )
    recorded_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[recorded_by_user_id],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<TrainingAttendance session={self.session_id!s:.8} "
            f"person={self.person_id!s:.8} status={self.status}>"
        )
