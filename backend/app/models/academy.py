"""Academy veri modelleri — program/modül/ders hiyerarşisi, kayıt, seans, ilerleme ve quiz."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.user import User


class AcademyProgram(Base):
    """Ders programı — global katalog (club_id=None) veya kulübe özel."""

    __tablename__ = "academy_programs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    slug: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    ad: Mapped[str] = mapped_column(Text(), nullable=False)
    kod: Mapped[str] = mapped_column(Text(), nullable=False)  # D1, D2
    aciklama: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    seviye: Mapped[int] = mapped_column(Integer(), nullable=False, default=1)
    aktif: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    modules: Mapped[List["AcademyModule"]] = relationship(
        back_populates="program", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AcademyProgram {self.slug}>"


class AcademyModule(Base):
    """Program içindeki modül."""

    __tablename__ = "academy_modules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academy_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(Text(), nullable=False)
    ad: Mapped[str] = mapped_column(Text(), nullable=False)
    sira: Mapped[int] = mapped_column(Integer(), nullable=False, default=1)
    aktif: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    program: Mapped["AcademyProgram"] = relationship(back_populates="modules")
    lessons: Mapped[List["AcademyLesson"]] = relationship(
        back_populates="module", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AcademyModule {self.slug}>"


class AcademyLesson(Base):
    """Ders — slug global unique (tenant-agnostic içerik)."""

    __tablename__ = "academy_lessons"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    module_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academy_modules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    ad: Mapped[str] = mapped_column(Text(), nullable=False)
    aciklama: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    ders_tipi: Mapped[str] = mapped_column(Text(), nullable=False, default="knot")
    tahmini_sure_dk: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    sira: Mapped[int] = mapped_column(Integer(), nullable=False, default=1)
    aktif: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    module: Mapped["AcademyModule"] = relationship(back_populates="lessons")
    steps: Mapped[List["AcademyLessonStep"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan"
    )
    quiz_questions: Mapped[List["AcademyQuizQuestion"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan"
    )
    quiz_attempts: Mapped[List["AcademyQuizAttempt"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan"
    )
    sessions: Mapped[List["AcademySession"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan"
    )
    progresses: Mapped[List["AcademyProgress"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AcademyLesson {self.slug}>"


class AcademyLessonStep(Base):
    """Ders adımı (video, metin, quiz vb.)."""

    __tablename__ = "academy_lesson_steps"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academy_lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sira: Mapped[int] = mapped_column(Integer(), nullable=False)
    tip: Mapped[str] = mapped_column(Text(), nullable=False)
    baslik: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    data_json: Mapped[Optional[dict]] = mapped_column(JSON(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    lesson: Mapped["AcademyLesson"] = relationship(back_populates="steps")

    def __repr__(self) -> str:
        return f"<AcademyLessonStep lesson={self.lesson_id!s:.8} sira={self.sira}>"


class AcademyEnrollment(Base):
    """Öğrenci-program kaydı."""

    __tablename__ = "academy_enrollments"
    __table_args__ = (
        UniqueConstraint(
            "club_id", "person_id", "program_id",
            name="uq_academy_enrollments_club_person_program",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academy_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(Text(), nullable=False, default="active")
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    person: Mapped["Person"] = relationship(back_populates="academy_enrollments")

    def __repr__(self) -> str:
        return f"<AcademyEnrollment person={self.person_id!s:.8} program={self.program_id!s:.8}>"


class AcademySession(Base):
    """Ders seans kaydı — auth hesabı + kişi kimliği ayrımı."""

    __tablename__ = "academy_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academy_lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ip_hash: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)  # HMAC-SHA256, KVKK

    user: Mapped["User"] = relationship(
        back_populates="academy_sessions", foreign_keys=[user_id]
    )
    person: Mapped["Person"] = relationship(
        back_populates="academy_sessions", foreign_keys=[person_id]
    )
    lesson: Mapped["AcademyLesson"] = relationship(back_populates="sessions")

    def __repr__(self) -> str:
        return f"<AcademySession person={self.person_id!s:.8} lesson={self.lesson_id!s:.8}>"


class AcademyProgress(Base):
    """Kişi başına ders ilerleme durumu."""

    __tablename__ = "academy_progress"
    __table_args__ = (
        UniqueConstraint(
            "club_id", "person_id", "lesson_id",
            name="uq_academy_progress_club_person_lesson",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academy_lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tamamlandi: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    yuzde: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)  # 0-100, MAX logic
    toplam_sure_sn: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    son_adim_sira: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    person: Mapped["Person"] = relationship(back_populates="academy_progresses")
    lesson: Mapped["AcademyLesson"] = relationship(back_populates="progresses")

    def __repr__(self) -> str:
        return f"<AcademyProgress person={self.person_id!s:.8} lesson={self.lesson_id!s:.8} {self.yuzde}%>"


class AcademyQuizQuestion(Base):
    """Quiz sorusu — correct_letter yalnızca backend katmanında kullanılır."""

    __tablename__ = "academy_quiz_questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academy_lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sira: Mapped[int] = mapped_column(Integer(), nullable=False)
    soru_metni: Mapped[str] = mapped_column(Text(), nullable=False)
    options: Mapped[list] = mapped_column(JSON(), nullable=False)  # [{"harf": "A", "metin": "..."}]
    # SECURITY: Bu alan public API response schema'larına eklenmemeli.
    # Quiz doğrulaması yalnızca backend service katmanında yapılır.
    correct_letter: Mapped[str] = mapped_column(Text(), nullable=False)
    aciklama: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    lesson: Mapped["AcademyLesson"] = relationship(back_populates="quiz_questions")
    answers: Mapped[List["AcademyQuizAnswer"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AcademyQuizQuestion lesson={self.lesson_id!s:.8} sira={self.sira}>"


class AcademyQuizAttempt(Base):
    """Quiz girişimi kaydı."""

    __tablename__ = "academy_quiz_attempts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academy_lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    basladi_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    bitti_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dogru: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    toplam: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    gecti: Mapped[Optional[bool]] = mapped_column(Boolean(), nullable=True)  # None = henüz bitmedi

    person: Mapped["Person"] = relationship(back_populates="quiz_attempts")
    lesson: Mapped["AcademyLesson"] = relationship(back_populates="quiz_attempts")
    answers: Mapped[List["AcademyQuizAnswer"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AcademyQuizAttempt person={self.person_id!s:.8} lesson={self.lesson_id!s:.8}>"


class AcademyQuizAnswer(Base):
    """Girişim başına cevap kaydı."""

    __tablename__ = "academy_quiz_answers"
    __table_args__ = (
        UniqueConstraint(
            "attempt_id", "question_id",
            name="uq_academy_quiz_answers_attempt_question",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academy_quiz_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academy_quiz_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    secilen_harf: Mapped[str] = mapped_column(Text(), nullable=False)
    dogru_mu: Mapped[bool] = mapped_column(Boolean(), nullable=False)

    attempt: Mapped["AcademyQuizAttempt"] = relationship(back_populates="answers")
    question: Mapped["AcademyQuizQuestion"] = relationship(back_populates="answers")

    def __repr__(self) -> str:
        return f"<AcademyQuizAnswer attempt={self.attempt_id!s:.8} q={self.question_id!s:.8} harf={self.secilen_harf}>"
