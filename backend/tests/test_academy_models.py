"""Academy modeli testleri — 10 tablo, FK/constraint/ilişki doğrulaması."""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base
from app.models.academy import (
    AcademyEnrollment,
    AcademyLesson,
    AcademyLessonStep,
    AcademyModule,
    AcademyProgress,
    AcademyProgram,
    AcademyQuizAnswer,
    AcademyQuizAttempt,
    AcademyQuizQuestion,
    AcademySession,
)
from app.models.club import Club
from app.models.person import Person
from app.models.user import User


# ─── Yardımcı fonksiyonlar ─────────────────────────────────────────────────


async def _make_club(db: AsyncSession) -> Club:
    club = Club(
        id=uuid.uuid4(),
        slug=f"club-{uuid.uuid4().hex[:8]}",
        name="Test Kulübü",
        plan="starter",
        is_active=True,
        settings={},
    )
    db.add(club)
    await db.flush()
    return club


async def _make_person(db: AsyncSession, club_id: uuid.UUID) -> Person:
    person = Person(
        id=uuid.uuid4(),
        club_id=club_id,
        first_name="Test",
        last_name=f"Kisi-{uuid.uuid4().hex[:6]}",
    )
    db.add(person)
    await db.flush()
    return person


async def _make_user(db: AsyncSession, club_id: uuid.UUID) -> User:
    from app.core.security import hash_password
    user = User(
        id=uuid.uuid4(),
        club_id=club_id,
        email=f"user-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("Test1234!"),
        full_name="Test User",
        role="sporcu",
        is_active=True,
        is_deleted=False,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_program(db: AsyncSession, club_id=None) -> AcademyProgram:
    prog = AcademyProgram(
        id=uuid.uuid4(),
        club_id=club_id,
        slug=f"prog-{uuid.uuid4().hex[:8]}",
        ad="Temel Denizcilik",
        kod="D1",
        seviye=1,
        aktif=True,
    )
    db.add(prog)
    await db.flush()
    return prog


async def _make_module(db: AsyncSession, program_id: uuid.UUID) -> AcademyModule:
    mod = AcademyModule(
        id=uuid.uuid4(),
        program_id=program_id,
        slug=f"mod-{uuid.uuid4().hex[:8]}",
        ad="Modül 1",
        sira=1,
    )
    db.add(mod)
    await db.flush()
    return mod


async def _make_lesson(db: AsyncSession, module_id: uuid.UUID) -> AcademyLesson:
    lesson = AcademyLesson(
        id=uuid.uuid4(),
        module_id=module_id,
        slug=f"ders-{uuid.uuid4().hex[:8]}",
        ad="Test Dersi",
        ders_tipi="knot",
        sira=1,
    )
    db.add(lesson)
    await db.flush()
    return lesson


# ─── Testler ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tables_created() -> None:
    """Tüm 10 academy tablosu metadata'da mevcut olmalı."""
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "academy_programs",
        "academy_modules",
        "academy_lessons",
        "academy_lesson_steps",
        "academy_enrollments",
        "academy_sessions",
        "academy_progress",
        "academy_quiz_questions",
        "academy_quiz_attempts",
        "academy_quiz_answers",
    }
    missing = expected - table_names
    assert not missing, f"Eksik tablolar: {missing}"


@pytest.mark.asyncio
async def test_program_module_lesson_hierarchy(db_session: AsyncSession) -> None:
    """Program → Module → Lesson → Step zinciri oluşturulabilmeli."""
    prog = await _make_program(db_session)
    mod = await _make_module(db_session, prog.id)
    lesson = await _make_lesson(db_session, mod.id)

    step = AcademyLessonStep(
        id=uuid.uuid4(),
        lesson_id=lesson.id,
        sira=1,
        tip="video",
        baslik="Giriş Videosu",
        data_json={"url": "https://example.com/video.mp4"},
    )
    db_session.add(step)
    await db_session.flush()

    # İlişki traversal
    await db_session.refresh(lesson, ["steps"])
    assert len(lesson.steps) == 1
    assert lesson.steps[0].tip == "video"

    await db_session.refresh(mod, ["lessons"])
    assert len(mod.lessons) >= 1

    await db_session.refresh(prog, ["modules"])
    assert len(prog.modules) >= 1


@pytest.mark.asyncio
async def test_lesson_slug_global_unique(db_session: AsyncSession) -> None:
    """Aynı slug ikinci kez eklenmek istenince IntegrityError fırlatmalı."""
    prog = await _make_program(db_session)
    mod = await _make_module(db_session, prog.id)

    slug = f"unique-ders-{uuid.uuid4().hex[:8]}"
    lesson1 = AcademyLesson(
        id=uuid.uuid4(),
        module_id=mod.id,
        slug=slug,
        ad="Ders 1",
        ders_tipi="knot",
        sira=1,
    )
    db_session.add(lesson1)
    await db_session.flush()

    lesson2 = AcademyLesson(
        id=uuid.uuid4(),
        module_id=mod.id,
        slug=slug,  # aynı slug!
        ad="Ders 2",
        ders_tipi="video",
        sira=2,
    )
    db_session.add(lesson2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_program_club_id_nullable(db_session: AsyncSession) -> None:
    """Global program (club_id=None) oluşturulabilmeli."""
    prog = await _make_program(db_session, club_id=None)
    assert prog.id is not None
    assert prog.club_id is None


@pytest.mark.asyncio
async def test_enrollment_unique_constraint(db_session: AsyncSession) -> None:
    """(club_id, person_id, program_id) duplicate → IntegrityError."""
    club = await _make_club(db_session)
    person = await _make_person(db_session, club.id)
    prog = await _make_program(db_session)

    enroll1 = AcademyEnrollment(
        id=uuid.uuid4(),
        club_id=club.id,
        person_id=person.id,
        program_id=prog.id,
        status="active",
    )
    db_session.add(enroll1)
    await db_session.flush()

    enroll2 = AcademyEnrollment(
        id=uuid.uuid4(),
        club_id=club.id,
        person_id=person.id,
        program_id=prog.id,
        status="active",
    )
    db_session.add(enroll2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_progress_unique_constraint(db_session: AsyncSession) -> None:
    """(club_id, person_id, lesson_id) duplicate → IntegrityError."""
    club = await _make_club(db_session)
    person = await _make_person(db_session, club.id)
    prog = await _make_program(db_session)
    mod = await _make_module(db_session, prog.id)
    lesson = await _make_lesson(db_session, mod.id)

    p1 = AcademyProgress(
        id=uuid.uuid4(),
        club_id=club.id,
        person_id=person.id,
        lesson_id=lesson.id,
        tamamlandi=False,
        yuzde=0,
        toplam_sure_sn=0,
    )
    db_session.add(p1)
    await db_session.flush()

    p2 = AcademyProgress(
        id=uuid.uuid4(),
        club_id=club.id,
        person_id=person.id,
        lesson_id=lesson.id,
        tamamlandi=False,
        yuzde=50,
        toplam_sure_sn=300,
    )
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_session_requires_user_and_person(db_session: AsyncSession) -> None:
    """Session'da hem user hem person bağlantısı bulunmalı."""
    club = await _make_club(db_session)
    person = await _make_person(db_session, club.id)
    user = await _make_user(db_session, club.id)
    prog = await _make_program(db_session)
    mod = await _make_module(db_session, prog.id)
    lesson = await _make_lesson(db_session, mod.id)

    session = AcademySession(
        id=uuid.uuid4(),
        club_id=club.id,
        user_id=user.id,
        person_id=person.id,
        lesson_id=lesson.id,
    )
    db_session.add(session)
    await db_session.flush()

    assert session.user_id == user.id
    assert session.person_id == person.id
    assert session.lesson_id == lesson.id


@pytest.mark.asyncio
async def test_quiz_answer_unique_per_attempt(db_session: AsyncSession) -> None:
    """(attempt_id, question_id) duplicate → IntegrityError."""
    club = await _make_club(db_session)
    person = await _make_person(db_session, club.id)
    prog = await _make_program(db_session)
    mod = await _make_module(db_session, prog.id)
    lesson = await _make_lesson(db_session, mod.id)

    question = AcademyQuizQuestion(
        id=uuid.uuid4(),
        lesson_id=lesson.id,
        sira=1,
        soru_metni="Hangi düğüm tipi kullanılır?",
        options=[{"harf": "A", "metin": "Kelebek"}, {"harf": "B", "metin": "Boğum"}],
        correct_letter="A",
    )
    db_session.add(question)
    await db_session.flush()

    attempt = AcademyQuizAttempt(
        id=uuid.uuid4(),
        club_id=club.id,
        person_id=person.id,
        lesson_id=lesson.id,
        dogru=0,
        toplam=1,
    )
    db_session.add(attempt)
    await db_session.flush()

    ans1 = AcademyQuizAnswer(
        id=uuid.uuid4(),
        club_id=club.id,
        attempt_id=attempt.id,
        question_id=question.id,
        secilen_harf="A",
        dogru_mu=True,
    )
    db_session.add(ans1)
    await db_session.flush()

    ans2 = AcademyQuizAnswer(
        id=uuid.uuid4(),
        club_id=club.id,
        attempt_id=attempt.id,
        question_id=question.id,  # aynı soru!
        secilen_harf="B",
        dogru_mu=False,
    )
    db_session.add(ans2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_cross_club_progress_allowed(db_session: AsyncSession) -> None:
    """Aynı person farklı club_id ile iki ayrı progress kaydı oluşturabilmeli."""
    club1 = await _make_club(db_session)
    club2 = await _make_club(db_session)
    # Person club1'e ait ama progress her iki kulüp için ayrı kaydedilir
    person = await _make_person(db_session, club1.id)
    prog = await _make_program(db_session)
    mod = await _make_module(db_session, prog.id)
    lesson = await _make_lesson(db_session, mod.id)

    p1 = AcademyProgress(
        id=uuid.uuid4(),
        club_id=club1.id,
        person_id=person.id,
        lesson_id=lesson.id,
        yuzde=30,
        toplam_sure_sn=180,
    )
    p2 = AcademyProgress(
        id=uuid.uuid4(),
        club_id=club2.id,
        person_id=person.id,
        lesson_id=lesson.id,
        yuzde=80,
        toplam_sure_sn=900,
    )
    db_session.add_all([p1, p2])
    await db_session.flush()  # IntegrityError olmamalı

    assert p1.club_id == club1.id
    assert p2.club_id == club2.id


@pytest.mark.asyncio
async def test_lesson_cascade_deletes_steps(db_session: AsyncSession) -> None:
    """Lesson silinince ona bağlı steps de silinmeli (CASCADE)."""
    prog = await _make_program(db_session)
    mod = await _make_module(db_session, prog.id)
    lesson = await _make_lesson(db_session, mod.id)
    lesson_id = lesson.id

    step = AcademyLessonStep(
        id=uuid.uuid4(),
        lesson_id=lesson_id,
        sira=1,
        tip="metin",
        baslik="Açıklama",
    )
    db_session.add(step)
    await db_session.flush()
    step_id = step.id

    # Lesson'ı sil
    await db_session.delete(lesson)
    await db_session.flush()

    # Step de gitmiş olmalı
    from sqlalchemy import select
    result = await db_session.execute(
        select(AcademyLessonStep).where(AcademyLessonStep.id == step_id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_correct_letter_field_exists() -> None:
    """AcademyQuizQuestion modelinde correct_letter alanı tanımlı olmalı."""
    cols = {c.key for c in AcademyQuizQuestion.__table__.columns}
    assert "correct_letter" in cols, "correct_letter kolonu modelde bulunamadı"
    # Güvenlik notu: bu alan public response schema'larına dahil edilmemeli
    # (kontrol yalnızca model seviyesinde; Pydantic schema bu sprintte kapsam dışı)
