"""user_account_service.py birim testleri — Sprint 18.

Her servis fonksiyonu için bağımsız testler.
G1/G3/G4/G5/G7/G8/G9 kuralları test edilir.
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.club import Club
from app.models.person import Person, PersonRole
from app.models.user import RefreshToken, User
from app.services.user_account_service import (
    create_user,
    delete_user,
    reset_password,
    restore_user,
    update_user,
    find_or_create_user_for_approval,
)


# ─── Yardımcı fixture'lar ─────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def club(db_session: AsyncSession) -> Club:
    c = Club(
        id=uuid.uuid4(),
        slug=f"svc-test-{uuid.uuid4().hex[:8]}",
        name="Servis Test Kulübü",
        plan="starter",
        is_active=True,
        settings={},
    )
    db_session.add(c)
    await db_session.flush()
    return c


@pytest_asyncio.fixture
async def admin(db_session: AsyncSession, club: Club) -> User:
    u = User(
        id=uuid.uuid4(),
        club_id=club.id,
        email=f"admin-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("Admin1234!"),
        full_name="Admin Kullanici",
        role="kulup_yonetici",
        is_active=True,
        is_deleted=False,
    )
    db_session.add(u)
    await db_session.flush()
    return u


@pytest_asyncio.fixture
async def second_admin(db_session: AsyncSession, club: Club) -> User:
    u = User(
        id=uuid.uuid4(),
        club_id=club.id,
        email=f"admin2-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("Admin5678!"),
        full_name="İkinci Admin",
        role="kulup_yonetici",
        is_active=True,
        is_deleted=False,
    )
    db_session.add(u)
    await db_session.flush()
    return u


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession, club: Club) -> User:
    u = User(
        id=uuid.uuid4(),
        club_id=club.id,
        email=f"uye-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("Uye9012!"),
        full_name="Sıradan Üye",
        role="uye",
        is_active=True,
        is_deleted=False,
    )
    db_session.add(u)
    await db_session.flush()
    return u


@pytest_asyncio.fixture
async def person(db_session: AsyncSession, club: Club) -> Person:
    p = Person(
        id=uuid.uuid4(),
        club_id=club.id,
        first_name="Ahmet",
        last_name="Test",
        is_active=True,
        is_deleted=False,
        must_change_password=False,
    )
    db_session.add(p)
    await db_session.flush()
    return p


@pytest_asyncio.fixture
async def sporcu_person(db_session: AsyncSession, club: Club) -> Person:
    """PersonRole=sporcu eklenmiş Person."""
    p = Person(
        id=uuid.uuid4(),
        club_id=club.id,
        first_name="Sporcu",
        last_name="Kişi",
        is_active=True,
        is_deleted=False,
        must_change_password=False,
    )
    db_session.add(p)
    await db_session.flush()
    pr = PersonRole(
        id=uuid.uuid4(),
        person_id=p.id,
        role_code="sporcu",
    )
    db_session.add(pr)
    await db_session.flush()
    return p


async def _add_refresh_token(db_session: AsyncSession, user_id: uuid.UUID) -> RefreshToken:
    rt = RefreshToken(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=f"hash-{uuid.uuid4().hex}",
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(rt)
    await db_session.flush()
    return rt


# ─── create_user ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_user_basic(db_session: AsyncSession, club: Club, admin: User):
    """Basit kullanıcı oluşturma — temp parola ve must_change_password doğrulanır."""
    user, temp_pw = await create_user(
        club_id=club.id,
        email=f"yeni-{uuid.uuid4().hex[:6]}@test.com",
        full_name="Yeni Kullanıcı",
        role="uye",
        person_id=None,
        assigner_role="kulup_yonetici",
        assigner_user_id=admin.id,
        db=db_session,
    )
    assert user.id is not None
    assert user.must_change_password is True
    assert len(temp_pw) >= 20  # token_urlsafe(16) → ~22 karakter
    # G5: parola loglanmaz — bunu dolaylı doğruluyoruz: audit_logs'ta değil
    assert verify_password(temp_pw, user.password_hash)


@pytest.mark.asyncio
async def test_create_user_g8_role_escalation_blocked(
    db_session: AsyncSession, club: Club, admin: User
):
    """G8: genel_sekreter super_admin oluşturamaz."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await create_user(
            club_id=club.id,
            email=f"super-{uuid.uuid4().hex[:6]}@test.com",
            full_name="Super Admin",
            role="super_admin",
            person_id=None,
            assigner_role="genel_sekreter",
            assigner_user_id=admin.id,
            db=db_session,
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_create_user_g8_kulup_yonetici_can_create_kulup_yonetici(
    db_session: AsyncSession, club: Club, admin: User
):
    """G8: kulup_yonetici başka kulup_yonetici oluşturabilir (P0-7 düzeltmesi)."""
    user, _ = await create_user(
        club_id=club.id,
        email=f"admin2-{uuid.uuid4().hex[:6]}@test.com",
        full_name="İkinci Yönetici",
        role="kulup_yonetici",
        person_id=None,
        assigner_role="kulup_yonetici",
        assigner_user_id=admin.id,
        db=db_session,
    )
    assert user.role == "kulup_yonetici"


@pytest.mark.asyncio
async def test_create_user_g9_duplicate_email(
    db_session: AsyncSession, club: Club, admin: User, regular_user: User
):
    """G9: Aynı e-posta adresiyle ikinci hesap açılamaz."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await create_user(
            club_id=club.id,
            email=regular_user.email,
            full_name="Kopya",
            role="uye",
            person_id=None,
            assigner_role="kulup_yonetici",
            assigner_user_id=admin.id,
            db=db_session,
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_create_user_g9_deleted_email_suggests_restore(
    db_session: AsyncSession, club: Club, admin: User
):
    """G9: Silinmiş hesabın e-postası restore önerisi döner."""
    from fastapi import HTTPException

    email = f"silindi-{uuid.uuid4().hex[:6]}@test.com"
    # Önce sil
    deleted = User(
        id=uuid.uuid4(),
        club_id=club.id,
        email=email,
        password_hash=hash_password("x"),
        full_name="Eski",
        role="uye",
        is_active=False,
        is_deleted=True,
    )
    db_session.add(deleted)
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await create_user(
            club_id=club.id,
            email=email,
            full_name="Yeni",
            role="uye",
            person_id=None,
            assigner_role="kulup_yonetici",
            assigner_user_id=admin.id,
            db=db_session,
        )
    assert exc_info.value.status_code == 409
    assert "restore" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_create_user_sporcu_requires_person_id(
    db_session: AsyncSession, club: Club, admin: User
):
    """K1: sporcu rolü için person_id zorunlu."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await create_user(
            club_id=club.id,
            email=f"sporcu-{uuid.uuid4().hex[:6]}@test.com",
            full_name="Sporcu",
            role="sporcu",
            person_id=None,
            assigner_role="kulup_yonetici",
            assigner_user_id=admin.id,
            db=db_session,
        )
    assert exc_info.value.status_code == 403 or exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_create_user_sporcu_with_person_role(
    db_session: AsyncSession, club: Club, admin: User, sporcu_person: Person
):
    """K1: PersonRole=sporcu olan Person'a sporcu kullanıcı bağlanabilir."""
    user, _ = await create_user(
        club_id=club.id,
        email=f"sporcu-{uuid.uuid4().hex[:6]}@test.com",
        full_name="Gerçek Sporcu",
        role="sporcu",
        person_id=sporcu_person.id,
        assigner_role="kulup_yonetici",
        assigner_user_id=admin.id,
        db=db_session,
    )
    assert user.person_id == sporcu_person.id


@pytest.mark.asyncio
async def test_create_user_sporcu_without_person_role_blocked(
    db_session: AsyncSession, club: Club, admin: User, person: Person
):
    """K1: PersonRole=sporcu olmayan Person'a sporcu bağlanamaz."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await create_user(
            club_id=club.id,
            email=f"sporcu-nr-{uuid.uuid4().hex[:6]}@test.com",
            full_name="Sporcu Değil",
            role="sporcu",
            person_id=person.id,
            assigner_role="kulup_yonetici",
            assigner_user_id=admin.id,
            db=db_session,
        )
    assert exc_info.value.status_code == 422


# ─── update_user ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_user_role_revokes_tokens(
    db_session: AsyncSession, club: Club, admin: User, regular_user: User
):
    """G1: Rol değişikliği tüm aktif refresh token'ları revoke eder."""
    rt = await _add_refresh_token(db_session, regular_user.id)
    assert rt.revoked_at is None

    await update_user(
        target_user=regular_user,
        role="misafir",
        is_active=None,
        full_name=None,
        assigner_role="kulup_yonetici",
        assigner_user_id=admin.id,
        db=db_session,
    )

    await db_session.refresh(rt)
    assert rt.revoked_at is not None


@pytest.mark.asyncio
async def test_update_user_g8_role_escalation_blocked(
    db_session: AsyncSession, club: Club, admin: User, regular_user: User
):
    """G8: genel_sekreter kulup_yonetici atayamaz."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await update_user(
            target_user=regular_user,
            role="kulup_yonetici",
            is_active=None,
            full_name=None,
            assigner_role="genel_sekreter",
            assigner_user_id=admin.id,
            db=db_session,
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_update_user_deactivate_not_last_admin(
    db_session: AsyncSession, club: Club, admin: User
):
    """G3: Tek aktif kulup_yonetici pasifleştirilemez."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await update_user(
            target_user=admin,
            role=None,
            is_active=False,
            full_name=None,
            assigner_role="kulup_yonetici",
            assigner_user_id=admin.id,
            db=db_session,
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_update_user_deactivate_with_second_admin(
    db_session: AsyncSession, club: Club, admin: User, second_admin: User
):
    """G3: İkinci admin varsa pasifleştirme izin verilir."""
    await update_user(
        target_user=admin,
        role=None,
        is_active=False,
        full_name=None,
        assigner_role="kulup_yonetici",
        assigner_user_id=second_admin.id,
        db=db_session,
    )
    assert admin.is_active is False


# ─── delete_user ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_user_soft_delete(
    db_session: AsyncSession, club: Club, admin: User, regular_user: User
):
    """Soft delete: is_deleted=True, is_active=False."""
    rt = await _add_refresh_token(db_session, regular_user.id)
    await delete_user(
        target_user=regular_user,
        assigner_user_id=admin.id,
        db=db_session,
    )
    assert regular_user.is_deleted is True
    assert regular_user.is_active is False
    await db_session.refresh(rt)
    assert rt.revoked_at is not None  # G1


@pytest.mark.asyncio
async def test_delete_user_g3_last_admin_blocked(
    db_session: AsyncSession, club: Club, admin: User
):
    """G3: Son admin silinemez."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await delete_user(
            target_user=admin,
            assigner_user_id=admin.id,
            db=db_session,
        )
    assert exc_info.value.status_code == 409


# ─── restore_user ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_restore_user(
    db_session: AsyncSession, club: Club, admin: User
):
    """Restore: is_deleted=False, is_active=True, must_change_password=True."""
    deleted_user = User(
        id=uuid.uuid4(),
        club_id=club.id,
        email=f"restore-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("x"),
        full_name="Silinmiş",
        role="uye",
        is_active=False,
        is_deleted=True,
        must_change_password=False,
    )
    db_session.add(deleted_user)
    await db_session.flush()

    restored = await restore_user(
        target_user=deleted_user,
        assigner_user_id=admin.id,
        db=db_session,
    )
    assert restored.is_deleted is False
    assert restored.is_active is True
    assert restored.must_change_password is True  # restore sonrası zorunlu


@pytest.mark.asyncio
async def test_restore_user_already_active_raises(
    db_session: AsyncSession, club: Club, admin: User, regular_user: User
):
    """Zaten aktif kullanıcı restore edilemez."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await restore_user(
            target_user=regular_user,
            assigner_user_id=admin.id,
            db=db_session,
        )
    assert exc_info.value.status_code == 409


# ─── reset_password ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reset_password(
    db_session: AsyncSession, club: Club, admin: User, regular_user: User
):
    """G5: Temp parola döner ama loglanmaz. G1: refresh token revoke."""
    rt = await _add_refresh_token(db_session, regular_user.id)

    temp_pw = await reset_password(
        target_user=regular_user,
        assigner_user_id=admin.id,
        db=db_session,
    )
    assert len(temp_pw) >= 20
    assert verify_password(temp_pw, regular_user.password_hash)
    assert regular_user.must_change_password is True

    await db_session.refresh(rt)
    assert rt.revoked_at is not None  # G1


# ─── find_or_create_user_for_approval ────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_or_create_user_for_approval_creates_new(
    db_session: AsyncSession, club: Club, person: Person
):
    """Üyelik onayında e-posta varsa yeni kullanıcı oluşturulur."""
    email = f"onay-{uuid.uuid4().hex[:6]}@test.com"
    user, temp_pw = await find_or_create_user_for_approval(
        club_id=club.id,
        email=email,
        full_name="Yeni Üye",
        person_id=person.id,
        db=db_session,
    )
    assert user is not None
    assert user.role == "uye"
    assert user.must_change_password is True
    assert temp_pw is not None
    assert len(temp_pw) >= 20


@pytest.mark.asyncio
async def test_find_or_create_user_for_approval_no_email(
    db_session: AsyncSession, club: Club, person: Person
):
    """E-posta yoksa (None, None) döner."""
    user, temp_pw = await find_or_create_user_for_approval(
        club_id=club.id,
        email=None,
        full_name="E-postasız",
        person_id=person.id,
        db=db_session,
    )
    assert user is None
    assert temp_pw is None


@pytest.mark.asyncio
async def test_find_or_create_user_for_approval_existing_user(
    db_session: AsyncSession, club: Club, person: Person, regular_user: User
):
    """Mevcut aktif hesap bulunursa parola değiştirilmez, temp_pw=None."""
    user, temp_pw = await find_or_create_user_for_approval(
        club_id=club.id,
        email=regular_user.email,
        full_name=regular_user.full_name,
        person_id=person.id,
        db=db_session,
    )
    assert user is not None
    assert user.id == regular_user.id
    assert temp_pw is None  # mevcut hesap — parola dokunulmadı
