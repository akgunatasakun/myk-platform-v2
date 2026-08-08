"""Üyelik başvurusu onay servisi.

Başvuru `submitted → approved` geçişinde bu servis çağrılır.
Tek bir transaction içinde:
  1. İdempotent Person oluşturma (national_id + club_id üzerinden deduplicate)
  2. PersonRole("uye") atama
  3. Yarış koşuluna dayanıklı member_number üretimi
  4. User hesabı oluşturma (e-posta varsa)
  5. application.person_id güncelleme

Hata halinde tüm değişiklikler rollback edilir — çağıran kendi transaction'ını yönetir.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.membership_application import MembershipApplication
from app.models.person import Person, PersonRole
from app.models.user import User

logger = logging.getLogger(__name__)

# Geçici parola uzunluğu (kullanıcı ilk girişte değiştirmek zorunda)
_TEMP_PASSWORD_BYTES = 16


async def _generate_member_number(club_id: uuid.UUID, year: int, db: AsyncSession) -> str:
    """Yarış koşuluna dayanıklı üye numarası üret.

    Format: MYK-{YY}-{N:04d}  örn. MYK-26-0001
    application_counters ile aynı atomic upsert tekniği kullanılır.
    """
    try:
        engine = db.get_bind()
        dialect = engine.dialect.name
    except Exception:
        dialect = "postgresql"

    year_short = year % 100  # 2026 → 26

    if dialect == "postgresql":
        sql = text("""
            INSERT INTO member_counters (club_id, year, last_number)
            VALUES (:club_id, :year, 1)
            ON CONFLICT (club_id, year)
            DO UPDATE SET last_number = member_counters.last_number + 1
            RETURNING last_number
        """)
    else:
        sql = text("""
            INSERT INTO member_counters (club_id, year, last_number)
            VALUES (:club_id, :year, 1)
            ON CONFLICT (club_id, year)
            DO UPDATE SET last_number = last_number + 1
            RETURNING last_number
        """)

    result = await db.execute(sql, {"club_id": str(club_id), "year": year})
    row = result.fetchone()
    if row is None:
        raise RuntimeError("Üye numarası üretilemedi — member_counters RETURNING sonuç döndürmedi.")
    return f"MYK-{year_short:02d}-{row[0]:04d}"


async def _find_or_create_person(
    app: MembershipApplication,
    db: AsyncSession,
) -> tuple[Person, bool]:
    """İdempotent Person oluşturma.

    Eğer aynı kulüpte aynı TC kimlik numarasına sahip Person varsa onu döndür.
    TC numarası yoksa application_id üzerinden kontrol et.
    Hiçbiri yoksa yeni Person oluştur.

    Returns:
        (person, created) — created=True ise yeni oluşturuldu.
    """
    club_id = app.club_id

    # 1. Zaten application.person_id set edilmişse kullan
    if app.person_id:
        result = await db.execute(
            select(Person).where(
                Person.id == app.person_id,
                Person.club_id == club_id,
                Person.is_deleted.is_(False),
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.info("Onay servisi: mevcut Person kullanıldı (id=%s)", existing.id)
            return existing, False

    # 2. TC kimlik numarasıyla ara (tekrar başvuruda aynı kişiyi bul)
    if app.national_id:
        result = await db.execute(
            select(Person).where(
                Person.club_id == club_id,
                Person.national_id == app.national_id,
                Person.is_deleted.is_(False),
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.info(
                "Onay servisi: TC kimliği eşleşti, mevcut Person kullanıldı (id=%s)", existing.id
            )
            return existing, False

    # 3. Yeni Person oluştur
    person = Person(
        club_id=club_id,
        first_name=app.first_name or "",
        last_name=app.last_name or "",
        national_id=app.national_id,
        birth_date=app.birth_date,
        gender=app.gender,
        phone=app.phone,
        email=app.email,
        address=app.address,
        emergency_contact_name=app.emergency_contact_name,
        emergency_contact_phone=app.emergency_contact_phone,
        blood_type=app.blood_type,
        is_active=True,
    )
    db.add(person)
    await db.flush()  # id üretilsin
    logger.info("Onay servisi: yeni Person oluşturuldu (id=%s)", person.id)
    return person, True


async def _ensure_uye_role(person: Person, db: AsyncSession) -> None:
    """'uye' rolü yoksa ekle — idempotent."""
    result = await db.execute(
        select(PersonRole).where(
            PersonRole.person_id == person.id,
            PersonRole.role_code == "uye",
        )
    )
    if result.scalar_one_or_none() is None:
        db.add(PersonRole(person_id=person.id, role_code="uye"))
        await db.flush()


async def _find_or_create_user(
    person: Person,
    app: MembershipApplication,
    db: AsyncSession,
) -> tuple[Optional[User], Optional[str]]:
    """Kullanıcı hesabı oluştur — e-posta varsa.

    Returns:
        (user, temp_password)  — user=None e-posta yoksa
        temp_password — kullanıcıya e-posta ile iletilecek geçici şifre
    """
    if not app.email:
        return None, None

    club_id = app.club_id

    # E-posta bu kulüpte zaten kullanılıyor mu?
    result = await db.execute(
        select(User).where(
            User.club_id == club_id,
            User.email == app.email,
            User.is_deleted.is_(False),
        )
    )
    existing_user = result.scalar_one_or_none()
    if existing_user:
        # Mevcut kullanıcıyı person'a bağla (henüz bağlı değilse)
        if existing_user.person_id is None:
            existing_user.person_id = person.id
            await db.flush()
        logger.info(
            "Onay servisi: mevcut User kullanıldı (id=%s)", existing_user.id
        )
        return existing_user, None  # Parola değiştirilmiyor

    # Geçici parola üret
    temp_password = secrets.token_urlsafe(_TEMP_PASSWORD_BYTES)
    full_name = f"{app.first_name or ''} {app.last_name or ''}".strip() or app.email

    user = User(
        club_id=club_id,
        email=app.email,
        password_hash=hash_password(temp_password),
        full_name=full_name,
        role="uye",
        is_active=True,
        person_id=person.id,
    )
    db.add(user)

    # Yeni kullanıcı geçici parola ile oluşturuldu; ilk girişte parola değiştirmesi zorunlu.
    person.must_change_password = True
    await db.flush()
    logger.info("Onay servisi: yeni User oluşturuldu (id=%s)", user.id)
    return user, temp_password


async def process_approval(
    app: MembershipApplication,
    db: AsyncSession,
    approved_by_user_id: uuid.UUID,
) -> ApprovalResult:
    """Başvuru onayındaki tüm yan etkileri uygula.

    Çağıran zaten transaction içinde olmalı; bu fonksiyon flush eder, commit etmez.
    Herhangi bir adımda hata olursa exception fırlatılır — çağıran rollback yapar.
    """
    now = datetime.now(timezone.utc)

    # ── 1. Person ────────────────────────────────────────────────────────────
    person, person_created = await _find_or_create_person(app, db)

    # ── 2. PersonRole "uye" ───────────────────────────────────────────────────
    await _ensure_uye_role(person, db)

    # ── 3. member_number (yeni Person veya henüz numara yoksa) ───────────────
    if person.member_number is None:
        person.member_number = await _generate_member_number(
            app.club_id, now.year, db
        )
        await db.flush()

    # ── 4. User hesabı ───────────────────────────────────────────────────────
    user, temp_password = await _find_or_create_user(person, app, db)

    # ── 5. application.person_id güncelle ────────────────────────────────────
    if app.person_id != person.id:
        app.person_id = person.id

    return ApprovalResult(
        person=person,
        person_created=person_created,
        user=user,
        temp_password=temp_password,
        member_number=person.member_number,
    )


class ApprovalResult:
    """process_approval çıktısı — e-posta servisi için gerekli bilgileri taşır."""

    __slots__ = ("person", "person_created", "user", "temp_password", "member_number")

    def __init__(
        self,
        person: Person,
        person_created: bool,
        user: Optional[User],
        temp_password: Optional[str],
        member_number: str,
    ) -> None:
        self.person = person
        self.person_created = person_created
        self.user = user
        self.temp_password = temp_password
        self.member_number = member_number
