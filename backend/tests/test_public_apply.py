"""Halka açık üyelik başvurusu endpoint testleri — Sprint 5A.

Kabul kriterleri:
  - Kimlik doğrulama gerektirmez
  - Geçerli başvuru submitted durumunda oluşturulur
  - consent_accepted=False → 422
  - Bilinmeyen club_slug → 404
  - Zorunlu alan eksikse → 422
  - Oluşturulan başvurunun club_id doğru
  - application_number üretilir
  - Şifre sıfırlama: request her zaman 204 döner (timing saldırısı önleme)
  - Şifre sıfırlama: geçersiz token → 400
  - Şifre sıfırlama: başarılı confirm sonrası şifre değişir
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.club import Club
from app.models.membership_application import MembershipApplication
from app.models.person import Person
from app.models.user import PasswordResetToken, User
from app.core.security import hash_password


# ─── Testler — halka açık başvuru ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_public_apply_success(
    client: AsyncClient,
    test_club: Club,
) -> None:
    """Geçerli başvuru 201 döner ve submitted durumunda oluşturulur."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "Ayşe",
        "last_name": "Kılıç",
        "email": "ayse.kilic@test.com",
        "phone": "05321234567",
        "birth_date": "2012-03-10",
        "gender": "kadin",
        "national_id": "55555555555",
        "consent_accepted": True,
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "submitted"
    assert data["first_name"] == "Ayşe"
    assert data["application_number"] is not None
    assert data["club_id"] == str(test_club.id)


@pytest.mark.asyncio
async def test_public_apply_no_auth_required(
    client: AsyncClient,
    test_club: Club,
) -> None:
    """Authorization başlığı olmadan da 201 döner (no-auth endpoint)."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "Deniz",
        "last_name": "Aslan",
        "email": "deniz.aslan@test.com",
        "phone": "05330000000",
        "consent_accepted": True,
    }
    # Herhangi bir auth header göndermiyoruz
    resp = await client.post(
        "/api/v1/public/membership-applications",
        json=payload,
        headers={},  # Auth header yok
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_public_apply_consent_false(
    client: AsyncClient,
    test_club: Club,
) -> None:
    """consent_accepted=False → 422 Unprocessable Entity."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "Test",
        "last_name": "Kullanıcı",
        "email": "test@test.com",
        "phone": "05300000000",
        "consent_accepted": False,
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_public_apply_unknown_club_slug(
    client: AsyncClient,
) -> None:
    """Bilinmeyen club_slug → 404."""
    payload = {
        "club_slug": "bu-kulup-yok-xyz",
        "first_name": "Test",
        "last_name": "Kullanıcı",
        "email": "test@test.com",
        "phone": "05300000000",
        "consent_accepted": True,
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_public_apply_missing_required_fields(
    client: AsyncClient,
    test_club: Club,
) -> None:
    """Zorunlu alanlar eksikse 422 döner."""
    # first_name eksik
    payload = {
        "club_slug": test_club.slug,
        "last_name": "Test",
        "email": "test@test.com",
        "phone": "05300000000",
        "consent_accepted": True,
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_public_apply_invalid_email(
    client: AsyncClient,
    test_club: Club,
) -> None:
    """Geçersiz e-posta → 422."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "Test",
        "last_name": "Test",
        "email": "bu-email-degil",
        "phone": "05300000000",
        "consent_accepted": True,
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_public_apply_extra_fields_rejected(
    client: AsyncClient,
    test_club: Club,
) -> None:
    """model_config extra=forbid — bilinmeyen alan 422 döner."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "Test",
        "last_name": "Test",
        "email": "test@test.com",
        "phone": "05300000000",
        "consent_accepted": True,
        "unknown_field": "bu alan schema'da yok",
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_public_apply_stores_in_db(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Başvuru gerçekten veritabanına yazılır."""
    unique_email = f"db-check-{uuid.uuid4().hex[:6]}@test.com"
    payload = {
        "club_slug": test_club.slug,
        "first_name": "Veritabanı",
        "last_name": "Kontrol",
        "email": unique_email,
        "phone": "05311111111",
        "national_id": "66666666666",
        "consent_accepted": True,
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 201

    app_id = resp.json()["id"]
    result = await db_session.execute(
        select(MembershipApplication).where(MembershipApplication.id == uuid.UUID(app_id))
    )
    saved_app = result.scalar_one_or_none()
    assert saved_app is not None
    assert saved_app.email == unique_email
    assert saved_app.status == "submitted"
    assert saved_app.club_id == test_club.id
    assert saved_app.national_id == "66666666666"
    assert saved_app.consent_accepted_at is not None


# ─── Testler — şifre sıfırlama ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_password_reset_request_always_204(
    client: AsyncClient,
    test_club: Club,
) -> None:
    """Var olmayan kullanıcı için de 204 döner — timing saldırısı önleme."""
    resp = await client.post(
        "/api/v1/auth/reset-password/request",
        json={"club_slug": test_club.slug, "email": "yok@test.com"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_password_reset_request_invalid_club_204(
    client: AsyncClient,
) -> None:
    """Bilinmeyen kulüp için de 204 döner."""
    resp = await client.post(
        "/api/v1/auth/reset-password/request",
        json={"club_slug": "yok-kulup", "email": "test@test.com"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_password_reset_confirm_invalid_token(
    client: AsyncClient,
) -> None:
    """Geçersiz token → 400."""
    resp = await client.post(
        "/api/v1/auth/reset-password/confirm",
        json={"token": "gecersiz-token-xyz", "new_password": "YeniSifre123"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_password_reset_confirm_expired_token(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Süresi dolmuş token → 400."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    prt = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=2),  # geçmiş zaman
    )
    db_session.add(prt)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/reset-password/confirm",
        json={"token": raw_token, "new_password": "YeniSifre123"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_password_reset_confirm_success(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Geçerli token ile şifre değiştirilir ve token kullanıldı işaretlenir."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    prt = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(prt)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/reset-password/confirm",
        json={"token": raw_token, "new_password": "YeniSifre123"},
    )
    assert resp.status_code == 204

    # Token kullanıldı işaretlendi mi?
    await db_session.refresh(prt)
    assert prt.used_at is not None


@pytest.mark.asyncio
async def test_password_reset_confirm_token_single_use(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Token tek kullanımlık — ikinci kullanımda 400 döner."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    prt = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(prt)
    await db_session.flush()

    # İlk kullanım — başarılı
    resp1 = await client.post(
        "/api/v1/auth/reset-password/confirm",
        json={"token": raw_token, "new_password": "YeniSifre123"},
    )
    assert resp1.status_code == 204

    # İkinci kullanım — başarısız
    resp2 = await client.post(
        "/api/v1/auth/reset-password/confirm",
        json={"token": raw_token, "new_password": "BaskaSifre456"},
    )
    assert resp2.status_code == 400


@pytest.mark.asyncio
async def test_password_reset_confirm_short_password(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Kısa şifre (< 8 karakter) → 422."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    prt = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(prt)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/reset-password/confirm",
        json={"token": raw_token, "new_password": "kisa"},
    )
    assert resp.status_code == 422
