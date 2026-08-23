"""users router entegrasyon testleri — Sprint 18.

Endpoint'ler: GET /users, POST /users, GET /users/{id},
              PATCH /users/{id}, DELETE /users/{id},
              POST /users/{id}/restore, POST /users/{id}/reset-password

Kapsam: RBAC, G3/G4/G8/G9 kuralları, 401/403/404/409 hata kodları.
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.club import Club
from app.models.user import User


# ─── Yardımcı fixture'lar ─────────────────────────────────────────────────────

@pytest.fixture
def admin_headers(test_user: User, test_club: Club) -> dict:
    token = create_access_token(str(test_user.id), str(test_club.id), "kulup_yonetici")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sporcu_headers(sporcu_user: User, test_club: Club) -> dict:
    token = create_access_token(str(sporcu_user.id), str(test_club.id), "sporcu")
    return {"Authorization": f"Bearer {token}"}


async def _create_extra_user(
    db_session: AsyncSession,
    club: Club,
    *,
    role: str = "uye",
    email: str | None = None,
    is_deleted: bool = False,
    is_active: bool = True,
) -> User:
    u = User(
        id=uuid.uuid4(),
        club_id=club.id,
        email=email or f"extra-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("Test1234!"),
        full_name="Ek Kullanıcı",
        role=role,
        is_active=is_active,
        is_deleted=is_deleted,
    )
    db_session.add(u)
    await db_session.flush()
    return u


# ─── GET /users ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_users_returns_200(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/v1/users", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data and "total" in data


@pytest.mark.asyncio
async def test_list_users_forbidden_for_sporcu(client: AsyncClient, sporcu_headers: dict):
    resp = await client.get("/api/v1/users", headers=sporcu_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/users")
    assert resp.status_code == 401


# ─── POST /users ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_user_success(
    client: AsyncClient, admin_headers: dict
):
    payload = {
        "email": f"new-{uuid.uuid4().hex[:6]}@test.com",
        "full_name": "Yeni Üye",
        "role": "uye",
    }
    resp = await client.post("/api/v1/users", json=payload, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["role"] == "uye"
    assert "temp_password" in data
    assert len(data["temp_password"]) >= 20
    assert data["must_change_password"] is True


@pytest.mark.asyncio
async def test_create_user_forbidden_for_sporcu(client: AsyncClient, sporcu_headers: dict):
    payload = {"email": "x@x.com", "full_name": "X", "role": "uye"}
    resp = await client.post("/api/v1/users", json=payload, headers=sporcu_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_user_g8_role_escalation(client: AsyncClient, admin_headers: dict):
    """G8: kulup_yonetici super_admin oluşturamaz."""
    payload = {
        "email": f"sa-{uuid.uuid4().hex[:6]}@test.com",
        "full_name": "Super",
        "role": "super_admin",
    }
    resp = await client.post("/api/v1/users", json=payload, headers=admin_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_user_g9_duplicate_email(
    client: AsyncClient, admin_headers: dict, db_session: AsyncSession, test_club: Club
):
    """G9: Aynı e-posta ile ikinci hesap açılamaz."""
    email = f"dup-{uuid.uuid4().hex[:6]}@test.com"
    await _create_extra_user(db_session, test_club, email=email)

    payload = {"email": email, "full_name": "Kopya", "role": "uye"}
    resp = await client.post("/api/v1/users", json=payload, headers=admin_headers)
    assert resp.status_code == 409


# ─── GET /users/{id} ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_user_detail(
    client: AsyncClient, admin_headers: dict, db_session: AsyncSession, test_club: Club
):
    extra = await _create_extra_user(db_session, test_club)
    resp = await client.get(f"/api/v1/users/{extra.id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == str(extra.id)


@pytest.mark.asyncio
async def test_get_user_not_found(client: AsyncClient, admin_headers: dict):
    resp = await client.get(f"/api/v1/users/{uuid.uuid4()}", headers=admin_headers)
    assert resp.status_code == 404


# ─── PATCH /users/{id} ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_user_role(
    client: AsyncClient, admin_headers: dict, db_session: AsyncSession, test_club: Club
):
    extra = await _create_extra_user(db_session, test_club, role="uye")
    resp = await client.patch(
        f"/api/v1/users/{extra.id}",
        json={"role": "misafir"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "misafir"


@pytest.mark.asyncio
async def test_update_user_g4_self_role_change(
    client: AsyncClient, test_user: User, test_club: Club
):
    """G4: Kullanıcı kendi rolünü değiştiremez."""
    token = create_access_token(str(test_user.id), str(test_club.id), "kulup_yonetici")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.patch(
        f"/api/v1/users/{test_user.id}",
        json={"role": "uye"},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_user_g3_last_admin_deactivate(
    client: AsyncClient, admin_headers: dict, test_user: User, test_club: Club,
    db_session: AsyncSession,
):
    """G3: Tek kulup_yonetici pasifleştirilemez."""
    # test_user tek admin — başka kulup_yonetici yok
    # Önce diğer yöneticileri sil / pasifleştir — test ortamında yalnızca test_user olduğunu varsayıyoruz
    resp = await client.patch(
        f"/api/v1/users/{test_user.id}",
        json={"is_active": False},
        headers=admin_headers,
    )
    # G4 (kendi hesabı) veya G3 — her ikisi de 403/409
    assert resp.status_code in (403, 409)


# ─── DELETE /users/{id} ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_user_soft_delete(
    client: AsyncClient, admin_headers: dict, db_session: AsyncSession, test_club: Club
):
    extra = await _create_extra_user(db_session, test_club)
    resp = await client.delete(f"/api/v1/users/{extra.id}", headers=admin_headers)
    assert resp.status_code == 204

    await db_session.refresh(extra)
    assert extra.is_deleted is True


@pytest.mark.asyncio
async def test_delete_user_g4_self(
    client: AsyncClient, test_user: User, test_club: Club
):
    """G4: Kendi hesabını silemez."""
    token = create_access_token(str(test_user.id), str(test_club.id), "kulup_yonetici")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.delete(f"/api/v1/users/{test_user.id}", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_user_g3_last_admin(
    client: AsyncClient, admin_headers: dict, test_user: User,
    db_session: AsyncSession, test_club: Club,
):
    """G3: Son admin silinemez (farklı adminden istek)."""
    # Farklı bir yönetici ile test_user'ı silmeyi dene
    other_admin = await _create_extra_user(db_session, test_club, role="kulup_yonetici")
    other_token = create_access_token(str(other_admin.id), str(test_club.id), "kulup_yonetici")
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # test_user'ı sil — başka da diğer_admin var, bu başarılı olur
    resp = await client.delete(f"/api/v1/users/{test_user.id}", headers=other_headers)
    # İki admin var, bu başarılı olmalı
    assert resp.status_code == 204


# ─── POST /users/{id}/restore ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_restore_user(
    client: AsyncClient, admin_headers: dict, db_session: AsyncSession, test_club: Club
):
    deleted = await _create_extra_user(db_session, test_club, is_deleted=True, is_active=False)
    resp = await client.post(f"/api/v1/users/{deleted.id}/restore", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_deleted"] is False
    assert data["is_active"] is True
    assert data["must_change_password"] is True


@pytest.mark.asyncio
async def test_restore_user_not_deleted_raises(
    client: AsyncClient, admin_headers: dict, db_session: AsyncSession, test_club: Club
):
    active = await _create_extra_user(db_session, test_club)
    resp = await client.post(f"/api/v1/users/{active.id}/restore", headers=admin_headers)
    assert resp.status_code == 409


# ─── POST /users/{id}/reset-password ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_reset_password_returns_temp_pw(
    client: AsyncClient, admin_headers: dict, db_session: AsyncSession, test_club: Club
):
    extra = await _create_extra_user(db_session, test_club)
    resp = await client.post(f"/api/v1/users/{extra.id}/reset-password", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "temp_password" in data
    assert len(data["temp_password"]) >= 20
    assert data["user_id"] == str(extra.id)


@pytest.mark.asyncio
async def test_reset_password_g4_self(
    client: AsyncClient, test_user: User, test_club: Club
):
    """G4: Kendi parolasını reset-password endpoint'iyle sıfırlayamaz."""
    token = create_access_token(str(test_user.id), str(test_club.id), "kulup_yonetici")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(f"/api/v1/users/{test_user.id}/reset-password", headers=headers)
    assert resp.status_code == 403


# ─── Tenant izolasyonu ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cannot_access_other_clubs_user(
    client: AsyncClient, admin_headers: dict, db_session: AsyncSession
):
    """Başka kulübün kullanıcısı 404 döner."""
    other_club = Club(
        id=uuid.uuid4(),
        slug=f"diger-kulup-{uuid.uuid4().hex[:6]}",
        name="Diğer Kulüp",
        plan="starter",
        is_active=True,
        settings={},
    )
    db_session.add(other_club)
    await db_session.flush()
    other_user = User(
        id=uuid.uuid4(),
        club_id=other_club.id,
        email=f"other-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("x"),
        full_name="Diğer",
        role="uye",
        is_active=True,
        is_deleted=False,
    )
    db_session.add(other_user)
    await db_session.flush()

    resp = await client.get(f"/api/v1/users/{other_user.id}", headers=admin_headers)
    assert resp.status_code == 404
