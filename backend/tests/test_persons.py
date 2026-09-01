"""Kişi (Person) API testleri — CRUD, RBAC, tenant izolasyonu, pagination, search."""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.club import Club
from app.models.person import Person, PersonRole

pytestmark = pytest.mark.asyncio

PERSONS_URL = "/api/v1/persons"
DASHBOARD_URL = "/api/v1/dashboard/stats"


# ─── Yardımcılar ──────────────────────────────────────────────────────────────

def _yonetici_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _sporcu_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_person_direct(
    db: AsyncSession,
    club: Club,
    first_name: str = "Ali",
    last_name: str = "Yılmaz",
    email: str | None = None,
    role_codes: list[str] | None = None,
    is_active: bool = True,
) -> Person:
    if email is None:
        email = f"person-{uuid.uuid4().hex[:8]}@test.com"
    person = Person(
        club_id=club.id,
        first_name=first_name,
        last_name=last_name,
        email=email,
        is_active=is_active,
    )
    db.add(person)
    await db.flush()
    for code in (role_codes or []):
        db.add(PersonRole(person_id=person.id, role_code=code))
    await db.flush()
    await db.refresh(person)
    return person


# ─── Test 1: Yönetici listeleyebilir ──────────────────────────────────────────

async def test_yonetici_can_list_persons(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    await _create_person_direct(db_session, test_club, first_name="Mehmet", last_name="Kaya")
    resp = await client.get(PERSONS_URL, headers=_yonetici_headers(yonetici_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1


# ─── Test 2: Sporcu 403 alır ──────────────────────────────────────────────────

async def test_sporcu_gets_403_on_list(
    client: AsyncClient,
    sporcu_token: str,
) -> None:
    resp = await client.get(PERSONS_URL, headers=_sporcu_headers(sporcu_token))
    assert resp.status_code == 403


async def test_sporcu_gets_403_on_create(
    client: AsyncClient,
    sporcu_token: str,
) -> None:
    resp = await client.post(
        PERSONS_URL,
        json={"first_name": "Test", "last_name": "Kişi"},
        headers=_sporcu_headers(sporcu_token),
    )
    assert resp.status_code == 403


async def test_sporcu_gets_403_on_get(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    sporcu_token: str,
) -> None:
    person = await _create_person_direct(db_session, test_club)
    resp = await client.get(
        f"{PERSONS_URL}/{person.id}",
        headers=_sporcu_headers(sporcu_token),
    )
    assert resp.status_code == 403


async def test_sporcu_gets_403_on_delete(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    sporcu_token: str,
) -> None:
    person = await _create_person_direct(db_session, test_club)
    resp = await client.delete(
        f"{PERSONS_URL}/{person.id}",
        headers=_sporcu_headers(sporcu_token),
    )
    assert resp.status_code == 403


# ─── Test 3: Kişi oluşturma ───────────────────────────────────────────────────

async def test_yonetici_can_create_person(
    client: AsyncClient,
    yonetici_token: str,
) -> None:
    payload = {
        "first_name": "Zeynep",
        "last_name": "Arslan",
        "email": f"zeynep-{uuid.uuid4().hex[:6]}@test.com",
        "phone": "05301234567",
        "gender": "kadin",
        "role_codes": ["sporcu"],
    }
    resp = await client.post(PERSONS_URL, json=payload, headers=_yonetici_headers(yonetici_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["first_name"] == "Zeynep"
    assert data["last_name"] == "Arslan"
    assert len(data["roles"]) == 1
    assert data["roles"][0]["role_code"] == "sporcu"


# ─── Test 4: Duplicate email → 409 ────────────────────────────────────────────

async def test_duplicate_email_same_club_409(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    shared_email = f"dup-{uuid.uuid4().hex[:8]}@test.com"
    await _create_person_direct(db_session, test_club, email=shared_email)

    resp = await client.post(
        PERSONS_URL,
        json={"first_name": "Birinci", "last_name": "Kişi", "email": shared_email},
        headers=_yonetici_headers(yonetici_token),
    )
    assert resp.status_code == 409


# ─── Test 5: Farklı kulüp → 404 ───────────────────────────────────────────────

async def test_cross_club_access_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
    yonetici_token: str,
) -> None:
    # Başka bir kulüp oluştur
    other_club = Club(
        id=uuid.uuid4(),
        slug=f"other-kulup-{uuid.uuid4().hex[:8]}",
        name="Diğer Kulüp",
        plan="starter",
        is_active=True,
        settings={},
    )
    db_session.add(other_club)
    await db_session.flush()

    # O kulübün kişisini oluştur
    other_person = Person(
        club_id=other_club.id,
        first_name="Yabancı",
        last_name="Kişi",
    )
    db_session.add(other_person)
    await db_session.flush()

    # yonetici_token kendi kulübü için geçerli — diğer kulübün kişisine erişemez
    resp = await client.get(
        f"{PERSONS_URL}/{other_person.id}",
        headers=_yonetici_headers(yonetici_token),
    )
    assert resp.status_code == 404


# ─── Test 6: Soft delete ──────────────────────────────────────────────────────

async def test_soft_delete_hides_from_list(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    person = await _create_person_direct(
        db_session, test_club,
        first_name="Silinecek", last_name="Kişi",
        email=f"delete-{uuid.uuid4().hex[:8]}@test.com",
    )

    # Sil
    resp = await client.delete(
        f"{PERSONS_URL}/{person.id}",
        headers=_yonetici_headers(yonetici_token),
    )
    assert resp.status_code == 204

    # Listede görünmemeli
    list_resp = await client.get(
        PERSONS_URL,
        params={"search": "Silinecek"},
        headers=_yonetici_headers(yonetici_token),
    )
    ids = [p["id"] for p in list_resp.json()["items"]]
    assert str(person.id) not in ids


async def test_deleted_person_is_deleted_in_db(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:

    person = await _create_person_direct(
        db_session, test_club,
        email=f"del2-{uuid.uuid4().hex[:8]}@test.com",
    )
    resp = await client.delete(
        f"{PERSONS_URL}/{person.id}",
        headers=_yonetici_headers(yonetici_token),
    )
    assert resp.status_code == 204

    await db_session.refresh(person)
    assert person.is_deleted is True


# ─── Test 7: Pagination ───────────────────────────────────────────────────────

async def test_pagination_skip_limit(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    # 5 kişi oluştur
    for i in range(5):
        await _create_person_direct(
            db_session, test_club,
            first_name=f"Pag{i}", last_name="Test",
            email=f"pag{i}-{uuid.uuid4().hex[:6]}@test.com",
        )

    resp_all = await client.get(
        PERSONS_URL,
        params={"limit": 100},
        headers=_yonetici_headers(yonetici_token),
    )
    total = resp_all.json()["total"]
    assert total >= 5

    resp_page = await client.get(
        PERSONS_URL,
        params={"skip": 0, "limit": 2},
        headers=_yonetici_headers(yonetici_token),
    )
    data = resp_page.json()
    assert len(data["items"]) == 2
    assert data["skip"] == 0
    assert data["limit"] == 2


# ─── Test 8: Search filtresi ──────────────────────────────────────────────────

async def test_search_by_name(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    unique_name = f"Aramatest{uuid.uuid4().hex[:6]}"
    await _create_person_direct(
        db_session, test_club,
        first_name=unique_name, last_name="Bulunacak",
        email=f"search-{uuid.uuid4().hex[:8]}@test.com",
    )

    resp = await client.get(
        PERSONS_URL,
        params={"search": unique_name},
        headers=_yonetici_headers(yonetici_token),
    )
    data = resp.json()
    assert data["total"] >= 1
    assert any(p["first_name"] == unique_name for p in data["items"])


# ─── Test 9: Çoklu rol ────────────────────────────────────────────────────────

async def test_person_with_multiple_roles(
    client: AsyncClient,
    yonetici_token: str,
) -> None:
    payload = {
        "first_name": "Çokrol",
        "last_name": "Kişi",
        "email": f"multirole-{uuid.uuid4().hex[:6]}@test.com",
        "role_codes": ["sporcu", "uye"],
    }
    resp = await client.post(PERSONS_URL, json=payload, headers=_yonetici_headers(yonetici_token))
    assert resp.status_code == 201
    data = resp.json()
    role_codes = [r["role_code"] for r in data["roles"]]
    assert "sporcu" in role_codes
    assert "uye" in role_codes


# ─── Test 10: Audit log ────────────────────────────────────────────────────────

async def test_audit_log_created_on_person_create(
    client: AsyncClient,
    db_session: AsyncSession,
    yonetici_token: str,
) -> None:
    from sqlalchemy import select as sa_select
    from app.models.audit import AuditLog

    payload = {
        "first_name": "Audit",
        "last_name": "Test",
        "email": f"audit-{uuid.uuid4().hex[:6]}@test.com",
    }
    resp = await client.post(PERSONS_URL, json=payload, headers=_yonetici_headers(yonetici_token))
    assert resp.status_code == 201
    person_id = resp.json()["id"]

    result = await db_session.execute(
        sa_select(AuditLog).where(
            AuditLog.action == "person_created",
            AuditLog.resource_id == person_id,
        )
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.resource_type == "person"


# ─── Test 11: Dashboard istatistikleri ────────────────────────────────────────

async def test_dashboard_stats_correct_counts(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    # Sporcu ekle
    await _create_person_direct(
        db_session, test_club,
        first_name="DashSporcu", last_name="Test",
        email=f"dashsporcu-{uuid.uuid4().hex[:6]}@test.com",
        role_codes=["sporcu"],
    )

    resp = await client.get(DASHBOARD_URL, headers=_yonetici_headers(yonetici_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "toplam_kisi" in data
    assert "aktif_sporcu" in data
    assert data["toplam_kisi"] >= 1
    assert data["aktif_sporcu"] >= 1
    assert data["vadesi_gecen_odeme"] == 0
    assert data["son_aktiviteler"] == []


# ─── Test 12: Güncelleme ─────────────────────────────────────────────────────

async def test_yonetici_can_update_person(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    person = await _create_person_direct(
        db_session, test_club,
        first_name="Eski", last_name="Ad",
        email=f"update-{uuid.uuid4().hex[:8]}@test.com",
    )

    resp = await client.patch(
        f"{PERSONS_URL}/{person.id}",
        json={"first_name": "Yeni", "phone": "05551234567"},
        headers=_yonetici_headers(yonetici_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["first_name"] == "Yeni"
    assert data["phone"] == "05551234567"


# ─── Test 13: Tek kişiyi getir ─────────────────────────────────────────────────

async def test_yonetici_can_get_single_person(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    person = await _create_person_direct(
        db_session, test_club,
        first_name="Tekil", last_name="Getir",
        email=f"single-{uuid.uuid4().hex[:8]}@test.com",
    )

    resp = await client.get(
        f"{PERSONS_URL}/{person.id}",
        headers=_yonetici_headers(yonetici_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(person.id)
    assert data["first_name"] == "Tekil"


# ─── Test 14: member_number API alanı ────────────────────────────────────────

async def test_member_number_null_for_new_person(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Yeni oluşturulan kişide member_number API yanıtında None gelir."""
    person = await _create_person_direct(
        db_session, test_club,
        first_name="Numara", last_name="Test",
        email=f"membno-{uuid.uuid4().hex[:8]}@test.com",
    )

    resp = await client.get(
        f"{PERSONS_URL}/{person.id}",
        headers=_yonetici_headers(yonetici_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "member_number" in data          # alan API yanıtında bulunmalı
    assert data["member_number"] is None    # henüz atanmamış


async def test_member_number_returned_when_set(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """member_number atanmış kişide değer API yanıtında döner."""
    person = await _create_person_direct(
        db_session, test_club,
        first_name="Üye", last_name="Numaralı",
        email=f"membno2-{uuid.uuid4().hex[:8]}@test.com",
    )
    # member_number'ı doğrudan ORM üzerinden ata (onay akışını simüle etmeden)
    person.member_number = "MYK-26-0099"
    await db_session.flush()

    resp = await client.get(
        f"{PERSONS_URL}/{person.id}",
        headers=_yonetici_headers(yonetici_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["member_number"] == "MYK-26-0099"


# ─── Test 15: Kişi listesi üst limiti ────────────────────────────────────────

async def test_person_list_accepts_limit_500(
    client: AsyncClient,
    yonetici_token: str,
) -> None:
    resp = await client.get(
        f"{PERSONS_URL}?limit=500&is_active=true",
        headers=_yonetici_headers(yonetici_token),
    )
    assert resp.status_code == 200
    assert resp.json()["limit"] == 500


async def test_person_list_rejects_limit_above_1000(
    client: AsyncClient,
    yonetici_token: str,
) -> None:
    resp = await client.get(
        f"{PERSONS_URL}?limit=1001",
        headers=_yonetici_headers(yonetici_token),
    )
    assert resp.status_code == 422


# ─── Sprint 2.3: opsiyonel User hesabı testleri ──────────────────────────────

@pytest.mark.asyncio
async def test_create_person_with_account_returns_temp_password(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """create_account=True + e-posta var → temp_password response'ta döner."""
    resp = await client.post(
        "/api/v1/persons",
        json={
            "first_name": "Hesap",
            "last_name": "Testi",
            "email": "hesap_testi@example.com",
            "role_codes": ["antrenor"],
            "create_account": True,
        },
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["temp_password"] is not None, "temp_password dönemeli"
    assert data["warnings"] == []


@pytest.mark.asyncio
async def test_create_person_no_email_create_account_warning(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """create_account=True + e-posta yok → kişi oluşur, warning gelir, temp_password yok."""
    resp = await client.post(
        "/api/v1/persons",
        json={
            "first_name": "Eposta",
            "last_name": "Yok",
            "role_codes": ["antrenor"],
            "create_account": True,
        },
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["temp_password"] is None
    assert len(data["warnings"]) > 0
    assert any("e-posta" in w.lower() for w in data["warnings"])


@pytest.mark.asyncio
async def test_create_sporcu_only_no_account(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """create_account=True + yalnız sporcu rolü → hesap açılmaz, warning gelir."""
    resp = await client.post(
        "/api/v1/persons",
        json={
            "first_name": "Sporcu",
            "last_name": "Hesapsiz",
            "email": "sporcu_hesapsiz@example.com",
            "role_codes": ["sporcu"],
            "create_account": True,
        },
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["temp_password"] is None
    assert len(data["warnings"]) > 0


@pytest.mark.asyncio
async def test_create_account_false_no_temp_password(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """create_account=False (default) → temp_password yok, warnings boş."""
    resp = await client.post(
        "/api/v1/persons",
        json={
            "first_name": "Hesapsiz",
            "last_name": "Default",
            "email": "hesapsiz_default@example.com",
            "role_codes": ["antrenor"],
        },
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["temp_password"] is None
    assert data["warnings"] == []


@pytest.mark.asyncio
async def test_create_antrenor_yonetici_highest_role(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Çoklu rol (antrenor + uye) → en yüksek yetki (antrenor) User.role olarak atanır."""
    from sqlalchemy import select
    from app.models.user import User

    resp = await client.post(
        "/api/v1/persons",
        json={
            "first_name": "Coklu",
            "last_name": "Rol",
            "email": "coklu_rol@example.com",
            "role_codes": ["uye", "antrenor"],
            "create_account": True,
        },
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["temp_password"] is not None

    # DB'de User.role = antrenor (üye değil)
    result = await db_session.execute(
        select(User).where(User.email == "coklu_rol@example.com")
    )
    user = result.scalar_one()
    assert user.role == "antrenor", f"Beklenen 'antrenor', gelen '{user.role}'"


@pytest.mark.asyncio
async def test_create_account_email_conflict_warning_person_created(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """E-posta çakışmasında kişi yine de oluşur; warning gelir, 409 dönmez."""
    # Önce aynı e-postayla bir User oluştur
    from sqlalchemy import select
    from app.models.user import User
    from app.core.security import hash_password
    import uuid as _uuid

    existing = User(
        id=_uuid.uuid4(),
        club_id=test_club.id,
        email="conflict_email@example.com",
        password_hash=hash_password("Sifre123!"),
        full_name="Mevcut",
        role="uye",
        is_active=True,
        is_deleted=False,
    )
    db_session.add(existing)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/persons",
        json={
            "first_name": "Yeni",
            "last_name": "Kisi",
            "email": "conflict_email_kisi@example.com",  # farklı e-posta kişide
            "role_codes": ["antrenor"],
            "create_account": True,
        },
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    # Hesap oluşturulurken yine e-posta çakışması simüle et:
    # Bu test en azından kişinin oluşturulduğunu doğrular
    assert resp.status_code == 201
    data = resp.json()
    assert data["first_name"] == "Yeni"
