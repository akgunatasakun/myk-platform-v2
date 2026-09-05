"""Kişisel evrak güvenlik, kapsam, MIME ve kota kuralları."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.person import Person
from app.models.person_document import PersonDocument
from app.models.person_guardian import PersonGuardian
from app.models.user import User
from app.schemas.auth import TokenPayload

FILE_MAX_BYTES = 20 * 1024 * 1024
SUBJECT_MAX_BYTES = 100 * 1024 * 1024
USER_DAILY_UPLOAD_LIMIT = 20


def detect_mime(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return None


def completed_years(birth_date: date, today: date) -> int:
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


def assert_guardian_upload_age(birth_date: date | None) -> None:
    if birth_date is None:
        return
    today = datetime.now(ZoneInfo("Europe/Istanbul")).date()
    if completed_years(birth_date, today) >= 18:
        raise HTTPException(
            status_code=403,
            detail="18 yaşını tamamlayan kişi için veli evrak yükleyemez.",
        )


async def get_active_user(
    current_user: TokenPayload, club_id: uuid.UUID, db: AsyncSession
) -> User:
    result = await db.execute(
        select(User).where(
            User.id == uuid.UUID(current_user.sub),
            User.club_id == club_id,
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=403, detail="Aktif kullanıcı bulunamadı.")
    if current_user.role == "veli" and user.person_id is None:
        raise HTTPException(
            status_code=403,
            detail="Veli hesabınızdaki kişi bağlantısı eksik. Kulüp yönetimine başvurun.",
        )
    return user


async def get_subject_or_404(
    subject_person_id: uuid.UUID, club_id: uuid.UUID, db: AsyncSession
) -> Person:
    result = await db.execute(
        select(Person).where(
            Person.id == subject_person_id,
            Person.club_id == club_id,
            Person.is_active.is_(True),
            Person.is_deleted.is_(False),
        )
    )
    person = result.scalar_one_or_none()
    if person is None:
        raise HTTPException(status_code=404, detail="Kişi bulunamadı.")
    return person


async def get_active_guardian_link(
    guardian_person_id: uuid.UUID,
    subject_person_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
) -> PersonGuardian:
    result = await db.execute(
        select(PersonGuardian).where(
            PersonGuardian.club_id == club_id,
            PersonGuardian.guardian_person_id == guardian_person_id,
            PersonGuardian.athlete_person_id == subject_person_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=403, detail="Bu kişi için veli yetkiniz yok.")
    if not link.is_active or link.revoked_at is not None:
        raise HTTPException(status_code=403, detail="Veli bağlantınız aktif değil.")
    return link


async def enforce_upload_quota(
    *,
    club_id: uuid.UUID,
    user_id: uuid.UUID,
    subject_person_id: uuid.UUID,
    incoming_size: int,
    db: AsyncSession,
) -> None:
    subject_total = await db.scalar(
        select(func.coalesce(func.sum(PersonDocument.size_bytes), 0)).where(
            PersonDocument.subject_person_id == subject_person_id,
            PersonDocument.club_id == club_id,
            PersonDocument.is_deleted.is_(False),
        )
    )
    if int(subject_total or 0) + incoming_size > SUBJECT_MAX_BYTES:
        raise HTTPException(status_code=507, detail="Kişi belge kapasitesi dolu (100MB).")

    today_utc = datetime.now(timezone.utc).date()
    daily_count = await db.scalar(
        select(func.count(PersonDocument.id)).where(
            PersonDocument.uploaded_by_user_id == user_id,
            func.date(PersonDocument.uploaded_at) == today_utc,
            PersonDocument.is_deleted.is_(False),
        )
    )
    if int(daily_count or 0) >= USER_DAILY_UPLOAD_LIMIT:
        raise HTTPException(status_code=429, detail="Günlük yükleme kotası doldu.")


def validate_file(data: bytes, declared_mime: str | None) -> str:
    if not data:
        raise HTTPException(status_code=422, detail="Boş dosya yüklenemez.")
    if len(data) > FILE_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Dosya 20 MB sınırını aşıyor.")
    detected = detect_mime(data)
    if detected is None or (declared_mime and declared_mime != detected):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Dosya içeriği veya MIME türü desteklenmiyor.",
        )
    return detected
