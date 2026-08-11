"""Kişi (Person) modeli — sporcular, üyeler, veliler ve diğer kulüp bağlantılı kişiler."""
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.membership_application import MembershipApplication
    from app.models.person_guardian import PersonGuardian
    from app.models.academy import AcademyEnrollment, AcademyProgress, AcademySession, AcademyQuizAttempt
    from app.models.training import TrainingEnrollment, TrainingAttendance
    from app.models.payment import Payment
    from app.models.equipment import Equipment


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    national_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    birth_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    blood_type: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    member_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    avatar_object_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    roles: Mapped[list["PersonRole"]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    membership_applications: Mapped[List["MembershipApplication"]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
    )

    # Veli-sporcu bağlantıları — her iki taraf için
    # "Bu kişi sporcu olarak" → veliieri
    athlete_guardian_links: Mapped[List["PersonGuardian"]] = relationship(
        foreign_keys="PersonGuardian.athlete_person_id",
        back_populates="athlete",
        cascade="all, delete-orphan",
    )
    # "Bu kişi veli olarak" → sporcuları
    guardian_links: Mapped[List["PersonGuardian"]] = relationship(
        foreign_keys="PersonGuardian.guardian_person_id",
        back_populates="guardian",
        cascade="all, delete-orphan",
    )

    # Academy ilişkileri
    academy_enrollments: Mapped[List["AcademyEnrollment"]] = relationship(
        back_populates="person"
    )
    academy_progresses: Mapped[List["AcademyProgress"]] = relationship(
        back_populates="person"
    )
    academy_sessions: Mapped[List["AcademySession"]] = relationship(
        back_populates="person", foreign_keys="AcademySession.person_id"
    )
    quiz_attempts: Mapped[List["AcademyQuizAttempt"]] = relationship(
        back_populates="person"
    )

    # Training ilişkileri
    training_enrollments: Mapped[List["TrainingEnrollment"]] = relationship(
        foreign_keys="TrainingEnrollment.person_id",
        back_populates="person",
    )
    training_attendances: Mapped[List["TrainingAttendance"]] = relationship(
        foreign_keys="TrainingAttendance.person_id",
        back_populates="person",
    )

    # Payment ilişkileri
    payments: Mapped[List["Payment"]] = relationship(
        foreign_keys="Payment.person_id",
        lazy="select",
    )

    # Equipment zimmet ilişkisi
    assigned_equipment: Mapped[List["Equipment"]] = relationship(
        foreign_keys="Equipment.assigned_person_id",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Person {self.first_name} {self.last_name}>"


class PersonRole(Base):
    __tablename__ = "person_roles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_code: Mapped[str] = mapped_column(String(20), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    person: Mapped["Person"] = relationship(back_populates="roles")

    def __repr__(self) -> str:
        return f"<PersonRole {self.role_code}>"
