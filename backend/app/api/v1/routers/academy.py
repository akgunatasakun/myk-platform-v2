"""Academy router — D1/İzbarço Backend MVP.

Prefix: /api/v1/academy
Tag: academy

Güvenlik kuralları:
- club_id her zaman JWT'den alınır, body'den ASLA kabul edilmez
- person_id her zaman User.person_id'den gelir
- Başka kulübün verisi → 404 (varlığı ifşa etmez)
- correct_letter API response'larına hiçbir koşulda eklenmez
- tamamlandi client body'sinden ASLA set edilmez; yalnızca quiz finish set eder
"""
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# KnotPlayer timeline dosyaları bu dizinde: backend/app/assets/knots/{slug}/timeline.json
_KNOT_ASSETS_DIR = Path(__file__).parents[3] / "assets" / "knots"

from app.config import get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.academy import (
    AcademyEnrollment,
    AcademyLesson,
    AcademyModule,
    AcademyProgress,
    AcademyProgram,
    AcademyQuizAnswer,
    AcademyQuizAttempt,
    AcademyQuizQuestion,
    AcademySession,
)
from app.models.person import Person
from app.models.user import User
from app.schemas.academy import (
    AcademyLessonOut,
    AcademyProgramListItem,
    AcademyProgramOut,
    EnrollmentCreate,
    EnrollmentOut,
    ProgressOut,
    QuizAnswerIn,
    QuizAttemptOut,
    QuizAttemptResult,
    QuizAttemptStartOut,
    QuizQuestionOut,
    SessionOut,
)
from app.schemas.auth import TokenPayload

settings = get_settings()
router = APIRouter(tags=["academy"])

_MAX_HEARTBEAT_DELTA_SEC = 20


# ── Yardımcı dependency'ler ───────────────────────────────────────────────────

async def get_current_person(
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Person:
    """JWT'deki user_id üzerinden bağlı Person'ı döndürür. Yoksa 403."""
    user_result = await db.execute(
        select(User).where(
            User.id == uuid.UUID(current_user.sub),
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        )
    )
    user = user_result.scalar_one_or_none()
    if user is None or user.person_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için Person kaydı gerekli.",
        )
    person = await db.get(Person, user.person_id)
    if person is None or person.club_id != uuid.UUID(current_user.club_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Geçersiz Person kaydı.",
        )
    return person


def _ip_hash(request: Request) -> str:
    """KVKK: IP adresi HMAC-SHA256 ile hashlenir, düz metin saklanmaz."""
    client_ip = request.client.host if request.client else "unknown"
    return hmac.new(
        settings.secret_key.encode(),
        client_ip.encode(),
        hashlib.sha256,
    ).hexdigest()


async def _get_or_create_progress(
    db: AsyncSession,
    club_id: uuid.UUID,
    person_id: uuid.UUID,
    lesson_id: uuid.UUID,
) -> AcademyProgress:
    """Progress kaydını getir ya da sıfırdan oluştur (flush, commit yok)."""
    result = await db.execute(
        select(AcademyProgress).where(
            AcademyProgress.club_id == club_id,
            AcademyProgress.person_id == person_id,
            AcademyProgress.lesson_id == lesson_id,
        )
    )
    progress = result.scalar_one_or_none()
    if progress is None:
        progress = AcademyProgress(
            club_id=club_id,
            person_id=person_id,
            lesson_id=lesson_id,
            tamamlandi=False,
            yuzde=0,
            toplam_sure_sn=0,
        )
        db.add(progress)
        await db.flush()
    return progress


# ── 1. Program listesi ────────────────────────────────────────────────────────

@router.get("/programs", response_model=list[AcademyProgramListItem])
async def list_programs(
    db: AsyncSession = Depends(get_db),
    _current_user: TokenPayload = Depends(get_current_user),
) -> list[AcademyProgramListItem]:
    """Tüm aktif programları döndür — global katalog, tenant filtresi yok."""
    result = await db.execute(
        select(AcademyProgram)
        .where(AcademyProgram.aktif.is_(True))
        .order_by(AcademyProgram.seviye)
    )
    programs = result.scalars().all()
    return [AcademyProgramListItem.model_validate(p) for p in programs]


# ── 2. Program detayı ─────────────────────────────────────────────────────────

@router.get("/programs/{slug}", response_model=AcademyProgramOut)
async def get_program(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _current_user: TokenPayload = Depends(get_current_user),
) -> AcademyProgramOut:
    """Program detayı — modüller ve dersler eager load."""
    result = await db.execute(
        select(AcademyProgram)
        .options(
            selectinload(AcademyProgram.modules).selectinload(
                AcademyModule.lessons
            ).selectinload(AcademyLesson.steps)
        )
        .where(AcademyProgram.slug == slug, AcademyProgram.aktif.is_(True))
    )
    program = result.scalar_one_or_none()
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program bulunamadı.")
    return AcademyProgramOut.model_validate(program)


# ── 3. Enrollment oluştur ─────────────────────────────────────────────────────

@router.post(
    "/programs/{program_id}/enroll",
    response_model=EnrollmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def enroll(
    program_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    current_person: Person = Depends(get_current_person),
    db: AsyncSession = Depends(get_db),
) -> EnrollmentOut:
    """Program kaydı oluştur — kulüp ve kişi JWT'den alınır."""
    club_id = uuid.UUID(current_user.club_id)

    # Program var mı?
    program = await db.get(AcademyProgram, program_id)
    if program is None or not program.aktif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program bulunamadı.")

    enrollment = AcademyEnrollment(
        club_id=club_id,
        person_id=current_person.id,
        program_id=program_id,
        status="active",
    )
    db.add(enrollment)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu programa zaten kayıtlısınız.",
        )
    return EnrollmentOut.model_validate(enrollment)


# ── 4. Mevcut kullanıcının enrollment'ları ────────────────────────────────────

@router.get("/me/enrollments", response_model=list[EnrollmentOut])
async def my_enrollments(
    current_user: TokenPayload = Depends(get_current_user),
    current_person: Person = Depends(get_current_person),
    db: AsyncSession = Depends(get_db),
) -> list[EnrollmentOut]:
    """JWT'deki kişinin enrollment'larını döndür."""
    club_id = uuid.UUID(current_user.club_id)
    result = await db.execute(
        select(AcademyEnrollment).where(
            AcademyEnrollment.club_id == club_id,
            AcademyEnrollment.person_id == current_person.id,
        )
    )
    enrollments = result.scalars().all()
    return [EnrollmentOut.model_validate(e) for e in enrollments]


# ── 5. Ders detayı ────────────────────────────────────────────────────────────

@router.get("/lessons/{slug}", response_model=AcademyLessonOut)
async def get_lesson(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _current_user: TokenPayload = Depends(get_current_user),
) -> AcademyLessonOut:
    """Global slug ile dersi ve adımlarını döndür."""
    result = await db.execute(
        select(AcademyLesson)
        .options(selectinload(AcademyLesson.steps))
        .where(AcademyLesson.slug == slug, AcademyLesson.aktif.is_(True))
    )
    lesson = result.scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ders bulunamadı.")
    return AcademyLessonOut.model_validate(lesson)


# ── 6. Session başlat ─────────────────────────────────────────────────────────

@router.post(
    "/lessons/{lesson_id}/sessions",
    response_model=SessionOut,
    status_code=status.HTTP_201_CREATED,
)
async def start_session(
    lesson_id: uuid.UUID,
    request: Request,
    current_user: TokenPayload = Depends(get_current_user),
    current_person: Person = Depends(get_current_person),
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    """Ders seansı başlat — enrollment kontrolü yapılır."""
    club_id = uuid.UUID(current_user.club_id)
    user_id = uuid.UUID(current_user.sub)

    # Ders var mı?
    lesson = await db.get(AcademyLesson, lesson_id)
    if lesson is None or not lesson.aktif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ders bulunamadı.")

    # Enrollment kontrolü: kişi bu dersin programına kayıtlı mı?
    enroll_result = await db.execute(
        select(AcademyEnrollment)
        .join(AcademyProgram, AcademyEnrollment.program_id == AcademyProgram.id)
        .join(AcademyModule, AcademyModule.program_id == AcademyProgram.id)
        .join(AcademyLesson, AcademyLesson.module_id == AcademyModule.id)
        .where(
            AcademyLesson.id == lesson_id,
            AcademyEnrollment.club_id == club_id,
            AcademyEnrollment.person_id == current_person.id,
        )
    )
    if enroll_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu derse erişim için önce programa kayıt olmanız gerekir.",
        )

    session = AcademySession(
        club_id=club_id,
        user_id=user_id,
        person_id=current_person.id,
        lesson_id=lesson_id,
        ip_hash=_ip_hash(request),
    )
    db.add(session)
    await db.flush()
    return SessionOut.model_validate(session)


# ── 7. Heartbeat ──────────────────────────────────────────────────────────────

@router.post("/sessions/{session_id}/heartbeat")
async def heartbeat(
    session_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    current_person: Person = Depends(get_current_person),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Aktif seans için kalp atışı — progress süresini günceller."""
    club_id = uuid.UUID(current_user.club_id)

    session = await db.get(AcademySession, session_id)
    # Başkasının session'ı → 404 (varlığı ifşa etmez)
    if (
        session is None
        or session.person_id != current_person.id
        or session.club_id != club_id
        or session.ended_at is not None
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seans bulunamadı.")

    now = datetime.now(timezone.utc)
    delta_sec = 0
    if session.last_heartbeat_at is not None:
        last = session.last_heartbeat_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        diff = (now - last).total_seconds()
        delta_sec = int(min(diff, _MAX_HEARTBEAT_DELTA_SEC))

    session.last_heartbeat_at = now

    # Progress güncelle
    progress = await _get_or_create_progress(
        db, club_id, current_person.id, session.lesson_id
    )
    progress.toplam_sure_sn += delta_sec
    progress.updated_at = now

    await db.flush()
    return {"ok": True, "toplam_sure_sn": progress.toplam_sure_sn}


# ── 8. Progress durumu ────────────────────────────────────────────────────────

@router.get("/lessons/{lesson_id}/progress", response_model=ProgressOut)
async def get_progress(
    lesson_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    current_person: Person = Depends(get_current_person),
    db: AsyncSession = Depends(get_db),
) -> ProgressOut:
    """Kişinin ders ilerleme durumunu döndür."""
    club_id = uuid.UUID(current_user.club_id)

    result = await db.execute(
        select(AcademyProgress).where(
            AcademyProgress.club_id == club_id,
            AcademyProgress.person_id == current_person.id,
            AcademyProgress.lesson_id == lesson_id,
        )
    )
    progress = result.scalar_one_or_none()
    if progress is None:
        # Kayıt yoksa sıfır döndür
        return ProgressOut(
            lesson_id=lesson_id,
            tamamlandi=False,
            yuzde=0,
            toplam_sure_sn=0,
            son_adim_sira=None,
        )
    return ProgressOut.model_validate(progress)


# ── 9. Quiz girişimi başlat ───────────────────────────────────────────────────

@router.post(
    "/lessons/{lesson_id}/quiz/attempts",
    response_model=QuizAttemptStartOut,
    status_code=status.HTTP_201_CREATED,
)
async def start_quiz_attempt(
    lesson_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    current_person: Person = Depends(get_current_person),
    db: AsyncSession = Depends(get_db),
) -> QuizAttemptStartOut:
    """Yeni quiz girişimi başlat — sorular correct_letter olmadan döndürülür."""
    club_id = uuid.UUID(current_user.club_id)

    # Ders var mı?
    lesson = await db.get(AcademyLesson, lesson_id)
    if lesson is None or not lesson.aktif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ders bulunamadı.")

    # Sorular var mı?
    q_result = await db.execute(
        select(AcademyQuizQuestion)
        .where(AcademyQuizQuestion.lesson_id == lesson_id)
        .order_by(AcademyQuizQuestion.sira)
    )
    questions = q_result.scalars().all()
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu ders için henüz soru eklenmemiş.",
        )

    # Aktif (bitmemiş) girişim var mı? Varsa 409
    active_result = await db.execute(
        select(AcademyQuizAttempt).where(
            AcademyQuizAttempt.club_id == club_id,
            AcademyQuizAttempt.person_id == current_person.id,
            AcademyQuizAttempt.lesson_id == lesson_id,
            AcademyQuizAttempt.bitti_at.is_(None),
        )
    )
    if active_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Zaten aktif bir quiz girişiminiz var. Önce bitirin.",
        )

    attempt = AcademyQuizAttempt(
        club_id=club_id,
        person_id=current_person.id,
        lesson_id=lesson_id,
        dogru=0,
        toplam=len(questions),
    )
    db.add(attempt)
    await db.flush()

    attempt_out = QuizAttemptOut.model_validate(attempt)
    questions_out = [QuizQuestionOut.model_validate(q) for q in questions]
    return QuizAttemptStartOut(attempt=attempt_out, questions=questions_out)


# ── 10. Cevap gönder ──────────────────────────────────────────────────────────

@router.post("/quiz/attempts/{attempt_id}/answers")
async def submit_answer(
    attempt_id: uuid.UUID,
    body: QuizAnswerIn,
    current_user: TokenPayload = Depends(get_current_user),
    current_person: Person = Depends(get_current_person),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Tek soru cevabı gönder — correct_letter ASLA response'a eklenmez."""
    club_id = uuid.UUID(current_user.club_id)

    attempt = await db.get(AcademyQuizAttempt, attempt_id)
    if (
        attempt is None
        or attempt.person_id != current_person.id
        or attempt.club_id != club_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Girişim bulunamadı.")

    if attempt.bitti_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu girişim zaten tamamlanmış.",
        )

    # Soru bu derse ait mi?
    question = await db.get(AcademyQuizQuestion, body.question_id)
    if question is None or question.lesson_id != attempt.lesson_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Soru bulunamadı.")

    # Doğruluk — yalnızca backend'de hesaplanır
    dogru_mu = body.secilen_harf.upper() == question.correct_letter.upper()

    answer = AcademyQuizAnswer(
        club_id=club_id,
        attempt_id=attempt_id,
        question_id=body.question_id,
        secilen_harf=body.secilen_harf.upper(),
        dogru_mu=dogru_mu,
    )
    db.add(answer)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu soruyu zaten cevapladınız.",
        )
    # correct_letter response'a EKLENMEz
    return {"ok": True}


# ── 11. Quiz bitir ────────────────────────────────────────────────────────────

@router.post("/quiz/attempts/{attempt_id}/finish", response_model=QuizAttemptResult)
async def finish_quiz_attempt(
    attempt_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    current_person: Person = Depends(get_current_person),
    db: AsyncSession = Depends(get_db),
) -> QuizAttemptResult:
    """Quiz girişimini bitir — sonuç hesaplanır, progress güncellenir."""
    club_id = uuid.UUID(current_user.club_id)

    attempt = await db.get(AcademyQuizAttempt, attempt_id)
    if (
        attempt is None
        or attempt.person_id != current_person.id
        or attempt.club_id != club_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Girişim bulunamadı.")

    if attempt.bitti_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu girişim zaten tamamlanmış.",
        )

    # Cevapları ve soruları birlikte çek
    answers_result = await db.execute(
        select(AcademyQuizAnswer)
        .options(selectinload(AcademyQuizAnswer.question))
        .where(AcademyQuizAnswer.attempt_id == attempt_id)
    )
    answers = answers_result.scalars().all()

    dogru_sayisi = sum(1 for a in answers if a.dogru_mu)
    toplam = attempt.toplam or len(answers) or 1
    gecti = (dogru_sayisi / toplam) >= 0.6

    now = datetime.now(timezone.utc)
    attempt.bitti_at = now
    attempt.dogru = dogru_sayisi
    attempt.toplam = toplam
    attempt.gecti = gecti

    # Progress güncelle
    progress = await _get_or_create_progress(
        db, club_id, current_person.id, attempt.lesson_id
    )
    if gecti:
        progress.tamamlandi = True
        progress.yuzde = 100
    else:
        # MAX mantığı — mevcut yuzde düşmesin
        yeni_yuzde = int((dogru_sayisi / toplam) * 100)
        if yeni_yuzde > progress.yuzde:
            progress.yuzde = yeni_yuzde
    progress.updated_at = now

    await db.flush()

    # Sonuç — doğru cevaplar bitişte gösterilebilir (quiz BİTMİŞ)
    sorular_result = []
    for a in answers:
        sorular_result.append({
            "soru_metni": a.question.soru_metni,
            "secilen": a.secilen_harf,
            "dogru_harf": a.question.correct_letter,
            "dogru_mu": a.dogru_mu,
            "aciklama": a.question.aciklama,
        })

    return QuizAttemptResult(
        attempt_id=attempt.id,
        dogru=dogru_sayisi,
        toplam=toplam,
        gecti=gecti,
        sorular=sorular_result,
    )


# ─────────────────────────────────────────────────────────────────────────────
# KnotPlayer timeline
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/knot/{slug}/timeline")
async def get_knot_timeline(
    slug: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """KnotPlayer timeline.json döndür.

    Dosya: backend/app/assets/knots/{slug}/timeline.json
    Auth: JWT gerekli (oturum açmış herhangi bir kullanıcı erişebilir).
    """
    # Slug path traversal koruması — yalnızca alfanümerik + tire + alt çizgi
    safe_chars = set("abcdefghijklmnopqrstuvwxyz0123456789-_")
    if not all(c in safe_chars for c in slug.lower()):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knot bulunamadı")

    timeline_path = _KNOT_ASSETS_DIR / slug / "timeline.json"
    if not timeline_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knot bulunamadı")

    return json.loads(timeline_path.read_text(encoding="utf-8"))
