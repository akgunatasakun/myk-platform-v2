"""Halka açık (auth gerektirmeyen) endpoint'ler.

- POST /public/membership-applications  — online üyelik başvurusu
- POST /auth/reset-password/request     — şifre sıfırlama e-postası
- POST /auth/reset-password/confirm     — yeni şifre belirleme
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.audit import log_action
from app.services.event_service import emit_event
from app.core.security import hash_password
from app.database import get_db
from app.enums import ProgramPreference
from app.models.club import Club
from app.models.membership_application import MembershipApplication
from app.models.user import PasswordResetToken, User
from app.schemas.membership import MembershipApplicationOut
from app.services.email_service import send_password_reset_email

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["public"])

# ── Şifre sıfırlama — token geçerlilik süresi ────────────────────────────────
_RESET_TOKEN_TTL_HOURS = 1


# ══════════════════════════════════════════════════════════════════════════════
# Halka açık üyelik başvurusu
# ══════════════════════════════════════════════════════════════════════════════

class PublicApplicationCreate(BaseModel):
    """Halka açık başvuru formu — kimlik doğrulama gerekmez."""
    model_config = {"extra": "forbid"}

    # Kulüp belirleme
    club_slug: str

    # Başvuru sahibi bilgileri
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    birth_date: str | None = None       # ISO 8601: "YYYY-MM-DD"
    gender: str | None = None           # "erkek" | "kadin" | "diger"
    national_id: str | None = None
    address: str | None = None
    blood_type: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    # Veli bilgileri (küçük sporcular için)
    guardian_name: str | None = None
    guardian_phone: str | None = None

    # Eğitim programı tercihi (opsiyonel) — tip ProgramPreference | None
    program_preference: ProgramPreference | None = None

    # KVKK onayı zorunlu
    consent_accepted: bool

    @field_validator("consent_accepted")
    @classmethod
    def consent_must_be_true(cls, v: bool) -> bool:
        if not v:
            raise ValueError("KVKK onayı zorunludur.")
        return v

    @field_validator("first_name", "last_name", "phone")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Bu alan boş bırakılamaz.")
        return v.strip()

    @field_validator("program_preference", mode="before")
    @classmethod
    def normalize_program(cls, v: object) -> str | None:
        """Enum dönüşümünden önce strip + lower + boş → None.

        Pydantic bu dönüşümden sonra değeri ProgramPreference'a coerce eder;
        geçersiz değerlerde ValidationError fırlar (allowlist'i burada tekrar etme).
        """
        if v is None or v == "":
            return None
        if not isinstance(v, str):
            raise ValueError("Program tercihi metin olmalıdır.")
        return v.strip().lower()


@router.post(
    "/public/membership-applications",
    response_model=MembershipApplicationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Halka açık üyelik başvurusu",
)
async def public_create_application(
    body: PublicApplicationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MembershipApplicationOut:
    """Kimlik doğrulama gerektirmeyen online üyelik başvurusu.

    Başvuru 'submitted' durumunda oluşturulur ve yönetici incelemesini bekler.
    """
    # Kulüp bul
    club_result = await db.execute(
        select(Club).where(Club.slug == body.club_slug, Club.is_active.is_(True))
    )
    club = club_result.scalar_one_or_none()
    if club is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kulüp bulunamadı.",
        )

    now = datetime.now(timezone.utc)

    # Başvuru numarası üret
    from app.api.v1.routers.memberships import _generate_application_number
    app_number = await _generate_application_number(club.id, now.year, db)

    # birth_date parse
    birth_date = None
    if body.birth_date:
        try:
            from datetime import date
            birth_date = date.fromisoformat(body.birth_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Geçersiz tarih formatı. YYYY-MM-DD kullanın.",
            )

    app = MembershipApplication(
        club_id=club.id,
        status="submitted",
        application_number=app_number,
        first_name=body.first_name,
        last_name=body.last_name,
        email=str(body.email),
        phone=body.phone,
        birth_date=birth_date,
        gender=body.gender,
        national_id=body.national_id,
        address=body.address,
        blood_type=body.blood_type,
        emergency_contact_name=body.emergency_contact_name,
        emergency_contact_phone=body.emergency_contact_phone,
        guardian_name=body.guardian_name,
        guardian_phone=body.guardian_phone,
        program_preference=body.program_preference.value if body.program_preference else None,
        submitted_at=now,
        consent_accepted_at=now,
        consent_text_version="v1",
    )
    db.add(app)
    await db.flush()

    _pp_value = body.program_preference.value if body.program_preference else None
    await log_action(
        db,
        action="public_membership_application_submitted",
        resource_type="membership_application",
        club_id=club.id,
        resource_id=str(app.id),
        after={
            "status": "submitted",
            "application_number": app_number,
            "email": str(body.email),
            "program_preference": _pp_value,
        },
        request=request,
    )

    await emit_event(
        db,
        club_id=club.id,
        event_type="application.submitted",
        aggregate_type="membership_application",
        aggregate_id=app.id,
        payload={
            "application_number": app_number,
            "first_name": body.first_name,
            "last_name": body.last_name,
            "program_preference": _pp_value,
        },
    )

    await db.commit()
    await db.refresh(app)
    return MembershipApplicationOut.from_orm_safe(app)


# ══════════════════════════════════════════════════════════════════════════════
# Şifre sıfırlama
# ══════════════════════════════════════════════════════════════════════════════

class PasswordResetRequestBody(BaseModel):
    model_config = {"extra": "forbid"}
    club_slug: str
    email: EmailStr


class PasswordResetConfirmBody(BaseModel):
    model_config = {"extra": "forbid"}
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Şifre en az 8 karakter olmalıdır.")
        return v


@router.post(
    "/auth/reset-password/request",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Şifre sıfırlama e-postası gönder",
)
async def reset_password_request(
    body: PasswordResetRequestBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Şifre sıfırlama bağlantısını e-posta ile gönderir.

    Kullanıcı bulunamasa da 204 döner — timing saldırısı önleme.
    """
    _no_content = Response(status_code=status.HTTP_204_NO_CONTENT)

    # Kulüp bul
    club_result = await db.execute(
        select(Club).where(Club.slug == body.club_slug, Club.is_active.is_(True))
    )
    club = club_result.scalar_one_or_none()
    if club is None:
        return _no_content

    # Kullanıcı bul
    user_result = await db.execute(
        select(User).where(
            User.club_id == club.id,
            User.email == str(body.email),
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        )
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        return _no_content

    # Raw token üret ve hash'le (yalnızca hash kaydedilir)
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    prt = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=_RESET_TOKEN_TTL_HOURS),
    )
    db.add(prt)

    await log_action(
        db,
        action="password_reset_requested",
        resource_type="user",
        club_id=club.id,
        user_id=user.id,
        request=request,
    )
    await db.commit()

    # E-posta gönder (transaction dışında)
    reset_url = f"{settings.frontend_base_url}/reset-password?token={raw_token}"
    try:
        await send_password_reset_email(to_email=str(body.email), reset_url=reset_url)
    except Exception as exc:
        logger.error("Şifre sıfırlama e-postası gönderilemedi: %s", exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/auth/reset-password/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Yeni şifre belirle",
)
async def reset_password_confirm(
    body: PasswordResetConfirmBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Token ile yeni şifre belirler.

    Token: tek kullanımlık, 1 saat geçerli.
    """
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()

    prt_result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
        )
    )
    prt = prt_result.scalar_one_or_none()

    if prt is None or not prt.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçersiz veya süresi dolmuş sıfırlama bağlantısı.",
        )

    # Kullanıcıyı bul
    user_result = await db.execute(
        select(User).where(
            User.id == prt.user_id,
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        )
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçersiz token.",
        )

    now = datetime.now(timezone.utc)

    # Şifre güncelle, token'ı kullanıldı işaretle
    user.password_hash = hash_password(body.new_password)
    prt.used_at = now

    # must_change_password Person modelinde tutulur, User'da değil
    if user.person_id is not None:
        from app.models.person import Person as PersonModel
        person_result = await db.execute(
            select(PersonModel).where(PersonModel.id == user.person_id)
        )
        person = person_result.scalar_one_or_none()
        if person is not None:
            person.must_change_password = False

    # Bu kullanıcının diğer aktif reset token'larını da geçersiz kıl
    other_tokens_result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.id != prt.id,
            PasswordResetToken.used_at.is_(None),
        )
    )
    for other in other_tokens_result.scalars().all():
        other.used_at = now

    await log_action(
        db,
        action="password_reset_completed",
        resource_type="user",
        club_id=user.club_id,
        user_id=user.id,
        request=request,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
