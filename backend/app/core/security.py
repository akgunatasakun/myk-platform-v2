"""JWT token oluşturma, doğrulama ve Argon2id parola işlemleri."""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.schemas.auth import TokenPayload

settings = get_settings()

# Argon2id: OWASP önerilen parametreler
_ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)

_bearer = HTTPBearer(auto_error=False)


# ── Parola ────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# ── JWT ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    user_id: uuid.UUID,
    club_id: uuid.UUID,
    role: str,
) -> str:
    expire = _now() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "club_id": str(club_id),
        "role": role,
        "exp": expire,
        "iat": _now(),
        "iss": "myk-platform",
        "aud": "myk-client",
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token() -> tuple[str, str]:
    """(raw_token, hashed_token) döndürür. DB'ye hash kaydedilir."""
    raw = secrets.token_urlsafe(64)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def decode_access_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience="myk-client",
            issuer="myk-platform",
        )
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz token türü.")
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token süresi doldu.")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Geçersiz token: {e}")


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ── FastAPI Bağımlılığı ───────────────────────────────────────────────────

async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
    db: AsyncSession = Depends(get_db),
) -> TokenPayload:
    """Access token'ı Authorization header veya HttpOnly cookie'den alır.

    Sprint 18 — DB doğrulaması (G2):
    JWT imzası geçerli olsa bile DB'deki User durumu kontrol edilir:
      - is_active=False   → 401 (pasifleştirilmiş hesap)
      - is_deleted=True   → 401 (silinmiş hesap)
      - club_id uyuşmuyor → 401 (tenant tutarsızlığı)
      - DB role ≠ JWT role → 401 (rol değişti; yeniden login gerekiyor)

    Bu sayede rol/pasiflik değişikliği mevcut JWT'de anında etkili olur;
    token_version olmadan 60 dakikalık staleness sorunu giderilir.
    """
    from app.models.user import User  # circular import önlemi

    token: str | None = None

    # 1. Authorization: Bearer <token>
    if credentials:
        token = credentials.credentials

    # 2. HttpOnly cookie
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama gerekiyor.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)

    # DB doğrulaması
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(payload.sub))
    )
    user = result.scalar_one_or_none()

    if user is None or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hesap bulunamadı veya silinmiş.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hesap pasifleştirilmiş. Lütfen yöneticinizle iletişime geçin.",
        )

    if str(user.club_id) != payload.club_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token geçersiz.",
        )

    if user.role != payload.role:
        # Rol değişti — frontend yeniden login yaptırmalı
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yetki değişikliği algılandı. Lütfen yeniden giriş yapın.",
        )

    return payload
