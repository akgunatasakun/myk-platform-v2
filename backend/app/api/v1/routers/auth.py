"""Auth router — login, logout, refresh, setup."""
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.audit import log_action
from app.core.ratelimit import check_rate_limit, get_redis, reset_rate_limit
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.club import Club
from app.models.user import RefreshToken, User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    SetupRequest,
    TokenPayload,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)

_REFRESH_COOKIE = "refresh_token"
_ACCESS_COOKIE = "access_token"
_COOKIE_KWARGS = {
    "httponly": True,
    "samesite": "lax",
    "secure": settings.myk_env == "production",
}


# ─── helpers ──────────────────────────────────────────────────────────────────

def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        _ACCESS_COOKIE,
        access_token,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        **_COOKIE_KWARGS,
    )
    response.set_cookie(
        _REFRESH_COOKIE,
        refresh_token,
        max_age=settings.jwt_refresh_token_expire_days * 86400,
        **_COOKIE_KWARGS,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(_ACCESS_COOKIE)
    response.delete_cookie(_REFRESH_COOKIE)


# ─── endpoints ────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> TokenResponse:
    ip = request.client.host if request.client else "unknown"

    # Rate limit
    allowed, retry_after = await check_rate_limit(redis_client, body.club_slug, body.email, ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Çok fazla giriş denemesi. {retry_after} saniye bekleyin.",
            headers={"Retry-After": str(retry_after)},
        )

    # Kulüp bul
    club_result = await db.execute(select(Club).where(Club.slug == body.club_slug, Club.is_active.is_(True)))
    club = club_result.scalar_one_or_none()
    if club is None:
        # Timing saldırısını önlemek için gecikmeyi koru — kullanıcıya ayrıntı verme
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz kimlik bilgileri.")

    # Kullanıcı bul
    user_result = await db.execute(
        select(User).where(User.club_id == club.id, User.email == body.email, User.is_deleted.is_(False))
    )
    user = user_result.scalar_one_or_none()

    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        await log_action(db, action="login_failed", resource_type="user",
                         club_id=club.id, request=request, success=False,
                         error_detail="invalid credentials")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz kimlik bilgileri.")

    # Token oluştur
    access_token = create_access_token(str(user.id), str(user.club_id), user.role)
    raw_refresh, hashed_refresh = create_refresh_token()

    refresh_entry = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=hashed_refresh,
        expires_at=datetime.now(timezone.utc).replace(microsecond=0)
        .__class__.fromtimestamp(
            datetime.now(timezone.utc).timestamp() + settings.jwt_refresh_token_expire_days * 86400,
            tz=timezone.utc,
        ),
    )
    db.add(refresh_entry)

    user.last_login_at = datetime.now(timezone.utc)

    await reset_rate_limit(redis_client, body.club_slug, body.email, ip)
    await log_action(db, action="login_success", resource_type="user",
                     club_id=club.id, user_id=user.id, request=request, success=True)

    _set_auth_cookies(response, access_token, raw_refresh)

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    refresh_token_cookie: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
    body: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    raw_token = refresh_token_cookie or (body.refresh_token if body else None)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token bulunamadı.")

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    rt = result.scalar_one_or_none()

    if rt is None or not rt.is_valid:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz veya süresi dolmuş token.")

    user_result = await db.execute(
        select(User).where(User.id == rt.user_id, User.is_active.is_(True), User.is_deleted.is_(False))
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanıcı bulunamadı.")

    # Eski token'ı iptal et (token rotation)
    rt.revoked_at = datetime.now(timezone.utc)

    new_access = create_access_token(str(user.id), str(user.club_id), user.role)
    new_raw_refresh, new_hashed_refresh = create_refresh_token()

    new_rt = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=new_hashed_refresh,
        expires_at=datetime.now(timezone.utc).__class__.fromtimestamp(
            datetime.now(timezone.utc).timestamp() + settings.jwt_refresh_token_expire_days * 86400,
            tz=timezone.utc,
        ),
    )
    db.add(new_rt)

    _set_auth_cookies(response, new_access, new_raw_refresh)
    return TokenResponse(access_token=new_access, expires_in=settings.jwt_access_token_expire_minutes * 60)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token_cookie: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
    db: AsyncSession = Depends(get_db),
) -> None:
    if refresh_token_cookie:
        token_hash = hashlib.sha256(refresh_token_cookie.encode()).hexdigest()
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        rt = result.scalar_one_or_none()
        if rt and rt.revoked_at is None:
            rt.revoked_at = datetime.now(timezone.utc)
    _clear_auth_cookies(response)


@router.post("/setup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def setup(
    body: SetupRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    İlk kulüp + yönetici oluşturma.

    Erişim kuralı (öncelik sırasıyla):
    1. Production ortamında herhangi bir kulüp varsa: her zaman 403. İstisna yok.
    2. Development/test ortamında, sistemde kulüp yoksa: her zaman çalışır.
    3. Development/test ortamında, kulüp var ve allow_public_setup=True ise: çalışır.
    4. Diğer tüm durumlarda: 403.

    Not: Production'da config validator ALLOW_PUBLIC_SETUP=true'yu zaten reddeder,
    bu kontrol ek bir güvenlik katmanıdır.
    """
    # Sistemde herhangi bir kulüp var mı?
    any_club_result = await db.execute(select(Club).limit(1))
    any_club = any_club_result.scalar_one_or_none()

    # Production: kulüp varsa kesinlikle kapat
    if settings.is_production and any_club is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kurulum tamamlandı. Yeni kulüp oluşturmak için yönetici yetkisi gereklidir.",
        )

    # Development/test: kulüp varsa allow_public_setup kontrolü
    if any_club is not None and not settings.allow_public_setup:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kurulum kapalı. Yeni kulüp oluşturmak için yönetici yetkisi gereklidir.",
        )

    existing = await db.execute(select(Club).where(Club.slug == body.club_slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu slug zaten kullanımda.")

    club = Club(
        id=uuid.uuid4(),
        slug=body.club_slug,
        name=body.club_name,
        plan="starter",
        is_active=True,
        settings={},
    )
    db.add(club)

    user = User(
        id=uuid.uuid4(),
        club_id=club.id,
        email=body.admin_email,
        password_hash=hash_password(body.admin_password),
        full_name=body.admin_full_name,
        role="kulup_yonetici",
        is_active=True,
        is_deleted=False,
    )
    db.add(user)

    await log_action(db, action="setup_completed", resource_type="club",
                     club_id=club.id, user_id=user.id, success=True)

    # commit + refresh — server_default alanları (created_at) SQLite'de yüklemek için
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)
