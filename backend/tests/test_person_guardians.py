"""PersonGuardian endpoint testleri — veli-sporcu ilişkisi."""
import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.club import Club
from app.models.person import Person, PersonRole
from app.models.person_guardian import PersonGuardian
from app.models.user import User


# ─── Yardımcı fixture'lar ────────────────────────────────────────────────────


async def _make_person(db: AsyncSession, club_id: uuid.UUID, **kwargs) -> Person:
    """Hızlı person oluşturucu."""
    person = Person(
        club_id=club_id,
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name", f"Kisi-{uuid.uuid4().hex[:6]}"),
        birth_date=kwargs.get("birth_date"),
    )
    db.add(person)
    await db.flush()
    return person


@pytest_asyncio.fixture
async def athlete(db_session: AsyncSession, test_club: Club) -> Person:
    return await _make_person(db_session, test_club.id, first_name="Sporcu", last_name="Atlı")


@pytest_asyncio.fixture
async def guardian_person(db_session: AsyncSession, test_club: Club) -> Person:
    return await _make_person(db_session, test_club.id, first_name="Veli", last_name="Bekçi")


@pytest_asyncio.fixture
async def other_club(db_session: AsyncSession) -> Club:
    club = Club(
        id=uuid.uuid4(),
        slug=f"diger-kulup-{uuid.uuid4().hex[:6]}",
        name="Diğer Kulüp",
        plan="starter",
        is_active=True,
        settings={},
    )
    db_session.add(club)
    await db_session.flush()
    return club


@pytest_asyncio.fixture
async def other_club_person(db_session: AsyncSession, other_club: Club) -> Person:
    return await _make_person(db_session, other_club.id, first_name="Başka", last_name="Kişi")


# ─── Testler ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_guardians_empty(
    client: AsyncClient,
    test_club: Club,
    athlete: Person,
    yonetici_token: str,
) -> None:
    """Velisi olmayan sporcuda boş liste döner."""
    resp = await client.get(
        f"/api/v1/persons/{athlete.id}/guardians",
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_guardian_athletes_include_birth_date_for_age_display(
    client: AsyncClient,
    test_club: Club,
    guardian_person: Person,
    db_session: AsyncSession,
    yonetici_token: str,
) -> None:
    athlete = await _make_person(
        db_session,
        test_club.id,
        first_name="Yaşlı",
        last_name="Sporcu",
        birth_date=date(2015, 9, 4),
    )
    db_session.add(PersonGuardian(
        club_id=test_club.id,
        athlete_person_id=athlete.id,
        guardian_person_id=guardian_person.id,
    ))
    await db_session.flush()

    resp = await client.get(
        f"/api/v1/persons/{guardian_person.id}/athletes",
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )

    assert resp.status_code == 200
    assert resp.json()[0]["athlete"]["birth_date"] == "2015-09-04"


@pytest.mark.asyncio
async def test_add_guardian_success(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    athlete: Person,
    guardian_person: Person,
    yonetici_token: str,
) -> None:
    """Başarılı veli ekleme — 201 ve PersonGuardianOut alanları tam."""
    resp = await client.post(
        f"/api/v1/persons/{athlete.id}/guardians",
        headers={"Authorization": f"Bearer {yonetici_token}"},
        json={
            "guardian_person_id": str(guardian_person.id),
            "relationship_type": "anne",
            "is_primary": True,
            "can_pickup": True,
            "can_receive_notifications": True,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["athlete_person_id"] == str(athlete.id)
    assert data["guardian_person_id"] == str(guardian_person.id)
    assert data["relationship_type"] == "anne"
    assert data["is_primary"] is True
    assert data["can_pickup"] is True
    assert data["can_receive_notifications"] is True
    # Nested guardian özeti
    assert data["guardian"]["id"] == str(guardian_person.id)
    assert data["guardian"]["first_name"] == guardian_person.first_name
    assert data["guardian"]["last_name"] == guardian_person.last_name
    role_result = await db_session.execute(
        select(PersonRole).where(
            PersonRole.person_id == guardian_person.id,
            PersonRole.role_code == "veli",
        )
    )
    assert role_result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_list_guardians_after_add(
    client: AsyncClient,
    test_club: Club,
    athlete: Person,
    guardian_person: Person,
    db_session: AsyncSession,
    yonetici_token: str,
) -> None:
    """Veli eklendikten sonra listede görünür."""
    link = PersonGuardian(
        club_id=test_club.id,
        athlete_person_id=athlete.id,
        guardian_person_id=guardian_person.id,
        is_primary=True,
        can_pickup=True,
        can_receive_notifications=True,
    )
    db_session.add(link)
    await db_session.flush()

    resp = await client.get(
        f"/api/v1/persons/{athlete.id}/guardians",
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["guardian_person_id"] == str(guardian_person.id)


@pytest.mark.asyncio
async def test_add_duplicate_guardian_409(
    client: AsyncClient,
    test_club: Club,
    athlete: Person,
    guardian_person: Person,
    db_session: AsyncSession,
    yonetici_token: str,
) -> None:
    """Aynı sporcu-veli çifti tekrar eklenemez — 409."""
    link = PersonGuardian(
        club_id=test_club.id,
        athlete_person_id=athlete.id,
        guardian_person_id=guardian_person.id,
        is_primary=False,
    )
    db_session.add(link)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/persons/{athlete.id}/guardians",
        headers={"Authorization": f"Bearer {yonetici_token}"},
        json={
            "guardian_person_id": str(guardian_person.id),
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_add_self_as_guardian_422(
    client: AsyncClient,
    test_club: Club,
    athlete: Person,
    yonetici_token: str,
) -> None:
    """Kişi kendini veli olarak atayamaz — 422."""
    resp = await client.post(
        f"/api/v1/persons/{athlete.id}/guardians",
        headers={"Authorization": f"Bearer {yonetici_token}"},
        json={"guardian_person_id": str(athlete.id)},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_add_guardian_from_other_club_404(
    client: AsyncClient,
    test_club: Club,
    athlete: Person,
    other_club_person: Person,
    yonetici_token: str,
) -> None:
    """Başka kulüpten kişi veli atanamazsa 404 döner."""
    resp = await client.post(
        f"/api/v1/persons/{athlete.id}/guardians",
        headers={"Authorization": f"Bearer {yonetici_token}"},
        json={"guardian_person_id": str(other_club_person.id)},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_is_primary_uniqueness(
    client: AsyncClient,
    test_club: Club,
    athlete: Person,
    db_session: AsyncSession,
    yonetici_token: str,
) -> None:
    """Yeni primary veli atanınca mevcut primary False yapılır."""
    veli1 = await _make_person(db_session, test_club.id, first_name="Veli1", last_name="Birinci")
    veli2 = await _make_person(db_session, test_club.id, first_name="Veli2", last_name="İkinci")

    # veli1'i primary olarak ekle
    resp1 = await client.post(
        f"/api/v1/persons/{athlete.id}/guardians",
        headers={"Authorization": f"Bearer {yonetici_token}"},
        json={"guardian_person_id": str(veli1.id), "is_primary": True},
    )
    assert resp1.status_code == 201
    link1_id = resp1.json()["id"]

    # veli2'yi primary olarak ekle → veli1 primary=False olmalı
    resp2 = await client.post(
        f"/api/v1/persons/{athlete.id}/guardians",
        headers={"Authorization": f"Bearer {yonetici_token}"},
        json={"guardian_person_id": str(veli2.id), "is_primary": True},
    )
    assert resp2.status_code == 201

    # DB'de veli1 artık primary değil
    result = await db_session.execute(
        select(PersonGuardian).where(PersonGuardian.id == uuid.UUID(link1_id))
    )
    link1 = result.scalar_one()
    assert link1.is_primary is False


@pytest.mark.asyncio
async def test_patch_guardian_update_fields(
    client: AsyncClient,
    test_club: Club,
    athlete: Person,
    guardian_person: Person,
    db_session: AsyncSession,
    yonetici_token: str,
) -> None:
    """PATCH ile relationship_type ve can_pickup güncellenebilir."""
    link = PersonGuardian(
        club_id=test_club.id,
        athlete_person_id=athlete.id,
        guardian_person_id=guardian_person.id,
        relationship_type="baba",
        can_pickup=False,
        is_primary=False,
    )
    db_session.add(link)
    await db_session.flush()

    resp = await client.patch(
        f"/api/v1/persons/{athlete.id}/guardians/{link.id}",
        headers={"Authorization": f"Bearer {yonetici_token}"},
        json={"relationship_type": "anne", "can_pickup": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["relationship_type"] == "anne"
    assert data["can_pickup"] is True


@pytest.mark.asyncio
async def test_patch_guardian_set_primary(
    client: AsyncClient,
    test_club: Club,
    athlete: Person,
    db_session: AsyncSession,
    yonetici_token: str,
) -> None:
    """PATCH ile is_primary=True atanınca diğer primary temizlenir."""
    veli1 = await _make_person(db_session, test_club.id, first_name="PV1", last_name="X")
    veli2 = await _make_person(db_session, test_club.id, first_name="PV2", last_name="Y")

    link1 = PersonGuardian(
        club_id=test_club.id,
        athlete_person_id=athlete.id,
        guardian_person_id=veli1.id,
        is_primary=True,
    )
    link2 = PersonGuardian(
        club_id=test_club.id,
        athlete_person_id=athlete.id,
        guardian_person_id=veli2.id,
        is_primary=False,
    )
    db_session.add_all([link1, link2])
    await db_session.flush()

    # link2'yi primary yap
    resp = await client.patch(
        f"/api/v1/persons/{athlete.id}/guardians/{link2.id}",
        headers={"Authorization": f"Bearer {yonetici_token}"},
        json={"is_primary": True},
    )
    assert resp.status_code == 200
    assert resp.json()["is_primary"] is True

    # link1 artık primary değil
    await db_session.refresh(link1)
    assert link1.is_primary is False


@pytest.mark.asyncio
async def test_delete_guardian_204(
    client: AsyncClient,
    test_club: Club,
    athlete: Person,
    guardian_person: Person,
    db_session: AsyncSession,
    yonetici_token: str,
) -> None:
    """DELETE başarılı — 204 ve ardından GET'te boş liste."""
    link = PersonGuardian(
        club_id=test_club.id,
        athlete_person_id=athlete.id,
        guardian_person_id=guardian_person.id,
    )
    db_session.add(link)
    await db_session.flush()
    link_id = link.id

    resp = await client.delete(
        f"/api/v1/persons/{athlete.id}/guardians/{link_id}",
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 204

    # GET'te kayıt yok
    list_resp = await client.get(
        f"/api/v1/persons/{athlete.id}/guardians",
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_delete_nonexistent_guardian_404(
    client: AsyncClient,
    test_club: Club,
    athlete: Person,
    yonetici_token: str,
) -> None:
    """Olmayan veli bağlantısı silinmek istenirse 404."""
    resp = await client.delete(
        f"/api/v1/persons/{athlete.id}/guardians/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_guardian_tenant_isolation(
    client: AsyncClient,
    test_club: Club,
    other_club: Club,
    other_club_person: Person,
    db_session: AsyncSession,
    yonetici_token: str,
) -> None:
    """Başka kulübün sporcusuna erişim 404 döner (tenant izolasyonu)."""
    resp = await client.get(
        f"/api/v1/persons/{other_club_person.id}/guardians",
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_guardian_requires_auth(
    client: AsyncClient,
    test_club: Club,
    athlete: Person,
    guardian_person: Person,
) -> None:
    """Token olmadan veli ekleme 401 döner."""
    resp = await client.post(
        f"/api/v1/persons/{athlete.id}/guardians",
        json={"guardian_person_id": str(guardian_person.id)},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_add_guardian_requires_write_permission(
    client: AsyncClient,
    athlete: Person,
    guardian_person: Person,
    sporcu_token: str,
) -> None:
    """Menü görünürlüğünden bağımsız olarak API kişi yazma yetkisi ister."""
    resp = await client.post(
        f"/api/v1/persons/{athlete.id}/guardians",
        headers={"Authorization": f"Bearer {sporcu_token}"},
        json={"guardian_person_id": str(guardian_person.id)},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_relationship_type_too_long_422(
    client: AsyncClient,
    test_club: Club,
    athlete: Person,
    guardian_person: Person,
    yonetici_token: str,
) -> None:
    """30 karakteri aşan relationship_type 422 döner."""
    resp = await client.post(
        f"/api/v1/persons/{athlete.id}/guardians",
        headers={"Authorization": f"Bearer {yonetici_token}"},
        json={
            "guardian_person_id": str(guardian_person.id),
            "relationship_type": "a" * 31,
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_extra_fields_rejected_422(
    client: AsyncClient,
    test_club: Club,
    athlete: Person,
    guardian_person: Person,
    yonetici_token: str,
) -> None:
    """extra=forbid — bilinmeyen alan gönderilirse 422."""
    resp = await client.post(
        f"/api/v1/persons/{athlete.id}/guardians",
        headers={"Authorization": f"Bearer {yonetici_token}"},
        json={
            "guardian_person_id": str(guardian_person.id),
            "bilinmeyen_alan": "değer",
        },
    )
    assert resp.status_code == 422
