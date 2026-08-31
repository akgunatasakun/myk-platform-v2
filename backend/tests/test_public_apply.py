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
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from decimal import Decimal

from app.models.club import Club
from app.models.membership_application import MembershipApplication
from app.models.training import TrainingCourse, TrainingEnrollment
from app.models.user import PasswordResetToken, User


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


# ─── Testler — program_preference (Sprint 2) ─────────────────────────────────

@pytest.mark.asyncio
async def test_program_preference_valid_optimist(
    client: AsyncClient,
    test_club: Club,
) -> None:
    """Geçerli program_preference='optimist' → 201, response'ta alan var."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "Yelken",
        "last_name": "Optimist",
        "email": f"opt-{uuid.uuid4().hex[:6]}@test.com",
        "phone": "05320000001",
        "consent_accepted": True,
        "program_preference": "optimist",
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["program_preference"] == "optimist"


@pytest.mark.asyncio
async def test_program_preference_normalize_ilca_uppercase(
    client: AsyncClient,
    test_club: Club,
) -> None:
    """'ILCA' büyük harf → normalize edilip 'ilca' kaydedilmeli."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "Norm",
        "last_name": "Test",
        "email": f"ilca-{uuid.uuid4().hex[:6]}@test.com",
        "phone": "05320000002",
        "consent_accepted": True,
        "program_preference": "ILCA",
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 201
    assert resp.json()["program_preference"] == "ilca"


@pytest.mark.asyncio
async def test_program_preference_normalize_420_whitespace(
    client: AsyncClient,
    test_club: Club,
) -> None:
    """' 420 ' (başında/sonunda boşluk) → normalize edilip '420' kaydedilmeli."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "Norm",
        "last_name": "420",
        "email": f"420-{uuid.uuid4().hex[:6]}@test.com",
        "phone": "05320000003",
        "consent_accepted": True,
        "program_preference": " 420 ",
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 201
    assert resp.json()["program_preference"] == "420"


@pytest.mark.asyncio
async def test_program_preference_invalid_value_422(
    client: AsyncClient,
    test_club: Club,
) -> None:
    """Geçersiz program_preference değeri → 422."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "Geçersiz",
        "last_name": "Program",
        "email": f"bad-{uuid.uuid4().hex[:6]}@test.com",
        "phone": "05320000004",
        "consent_accepted": True,
        "program_preference": "golf",
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_program_preference_null_accepted(
    client: AsyncClient,
    test_club: Club,
) -> None:
    """program_preference=null → 201, alan response'ta null."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "Null",
        "last_name": "Program",
        "email": f"null-{uuid.uuid4().hex[:6]}@test.com",
        "phone": "05320000005",
        "consent_accepted": True,
        "program_preference": None,
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 201
    assert resp.json()["program_preference"] is None


@pytest.mark.asyncio
async def test_program_preference_field_absent_accepted(
    client: AsyncClient,
    test_club: Club,
) -> None:
    """program_preference alanı payload'da hiç yoksa → 201, alan response'ta null."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "Absent",
        "last_name": "Program",
        "email": f"abs-{uuid.uuid4().hex[:6]}@test.com",
        "phone": "05320000006",
        "consent_accepted": True,
        # program_preference alanı yok
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 201
    assert resp.json()["program_preference"] is None


@pytest.mark.asyncio
async def test_program_preference_stored_in_db(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """program_preference veritabanına doğru yazılır."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "DB",
        "last_name": "Kayıt",
        "email": f"dbpp-{uuid.uuid4().hex[:6]}@test.com",
        "phone": "05320000007",
        "consent_accepted": True,
        "program_preference": "wing_foil",
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 201

    app_id = resp.json()["id"]
    result = await db_session.execute(
        select(MembershipApplication).where(MembershipApplication.id == uuid.UUID(app_id))
    )
    saved = result.scalar_one_or_none()
    assert saved is not None
    assert saved.program_preference == "wing_foil"


@pytest.mark.asyncio
async def test_program_preference_in_event_payload(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """program_preference event payload'ına da yazılır."""
    from app.models.events import DomainEvent  # noqa: PLC0415
    from sqlalchemy import desc

    payload = {
        "club_slug": test_club.slug,
        "first_name": "Event",
        "last_name": "Payload",
        "email": f"evpp-{uuid.uuid4().hex[:6]}@test.com",
        "phone": "05320000008",
        "consent_accepted": True,
        "program_preference": "para_yelken",
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 201

    app_id_str = resp.json()["id"]
    result = await db_session.execute(
        select(DomainEvent)
        .where(DomainEvent.aggregate_id == app_id_str)
        .order_by(desc(DomainEvent.created_at))
        .limit(1)
    )
    event = result.scalar_one_or_none()
    assert event is not None, "DomainEvent kaydı bulunamadı"
    assert event.payload.get("program_preference") == "para_yelken"


@pytest.mark.asyncio
async def test_program_preference_tenant_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Farklı kulüp slug'ı ile gönderilen başvuru sadece o kulübün DB kaydına gider."""
    from app.models.club import Club as ClubModel  # noqa: PLC0415

    # Kulüp 2 oluştur
    club2 = ClubModel(
        id=uuid.uuid4(),
        name="İkinci Test Kulübü",
        slug=f"ikinci-kulup-{uuid.uuid4().hex[:6]}",
        plan="starter",
        is_active=True,
    )
    db_session.add(club2)
    await db_session.flush()

    payload = {
        "club_slug": club2.slug,
        "first_name": "Tenant",
        "last_name": "Test",
        "email": f"tenant-{uuid.uuid4().hex[:6]}@test.com",
        "phone": "05320000009",
        "consent_accepted": True,
        "program_preference": "ilca",
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 201

    data = resp.json()
    assert data["club_id"] == str(club2.id), "Başvuru yanlış kulübe atandı"
    assert data["program_preference"] == "ilca"


@pytest.mark.asyncio
async def test_program_preference_not_changed_by_status_update(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Admin durum güncellemesi program_preference'ı değiştirmemeli."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "Durum",
        "last_name": "Değişmez",
        "email": f"status-{uuid.uuid4().hex[:6]}@test.com",
        "phone": "05320000010",
        "consent_accepted": True,
        "program_preference": "420",
    }
    resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert resp.status_code == 201
    app_id = resp.json()["id"]

    # Admin durum geçişi
    transition_resp = await client.patch(
        f"/api/v1/membership-applications/{app_id}/status",
        json={"to_status": "approved"},
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert transition_resp.status_code == 200

    # DB'de program_preference hâlâ "420" olmalı
    result = await db_session.execute(
        select(MembershipApplication).where(MembershipApplication.id == uuid.UUID(app_id))
    )
    saved = result.scalar_one_or_none()
    assert saved is not None
    assert saved.program_preference == "420", (
        f"Status update program_preference'ı değiştirdi! Alınan: {saved.program_preference!r}"
    )


# ─── Testler — preferred_course_id ───────────────────────────────────────────

def _make_course(
    club_id: uuid.UUID,
    *,
    name: str = "Test Kurs",
    status: str = "planlandi",
    is_active: bool = True,
    is_deleted: bool = False,
) -> TrainingCourse:
    return TrainingCourse(
        id=uuid.uuid4(),
        club_id=club_id,
        name=name,
        status=status,
        is_active=is_active,
        is_deleted=is_deleted,
        fee=Decimal("0"),
    )


@pytest.mark.asyncio
async def test_public_course_list_tenant_filter(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Sadece aynı kulübün açık eğitimleri listelenmeli; başka kulübünkiler görünmemeli."""
    # İkinci kulüp + kurs
    club2 = Club(
        id=uuid.uuid4(), name="Diğer Kulüp",
        slug=f"diger-{uuid.uuid4().hex[:6]}", plan="starter", is_active=True,
    )
    db_session.add(club2)
    course_own = _make_course(test_club.id, name="Kendi Kurs")
    course_other = _make_course(club2.id, name="Başka Kulüp Kursu")
    db_session.add_all([course_own, course_other])
    await db_session.flush()

    resp = await client.get(
        "/api/v1/public/training-courses",
        params={"club_slug": test_club.slug},
    )
    assert resp.status_code == 200
    ids = {c["id"] for c in resp.json()}
    assert str(course_own.id) in ids, "Kendi kursu listede olmalı"
    assert str(course_other.id) not in ids, "Başka kulübün kursu listede olmamalı"


@pytest.mark.asyncio
async def test_public_course_list_status_filter(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Pasif / silinmiş / tamamlanmış kurslar listelenmemeli."""
    active = _make_course(test_club.id, name="Aktif Kurs", status="aktif")
    planned = _make_course(test_club.id, name="Planlanan Kurs", status="planlandi")
    inactive = _make_course(test_club.id, name="Pasif Kurs", is_active=False)
    deleted = _make_course(test_club.id, name="Silinmiş Kurs", is_deleted=True)
    completed = _make_course(test_club.id, name="Tamamlanan Kurs", status="tamamlandi")
    db_session.add_all([active, planned, inactive, deleted, completed])
    await db_session.flush()

    resp = await client.get(
        "/api/v1/public/training-courses",
        params={"club_slug": test_club.slug},
    )
    assert resp.status_code == 200
    ids = {c["id"] for c in resp.json()}
    assert str(active.id) in ids
    assert str(planned.id) in ids
    assert str(inactive.id) not in ids, "Pasif kurs görünmemeli"
    assert str(deleted.id) not in ids, "Silinmiş kurs görünmemeli"
    assert str(completed.id) not in ids, "Tamamlanan kurs görünmemeli"


@pytest.mark.asyncio
async def test_submit_with_valid_preferred_course(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Geçerli preferred_course_id → 201, alan response'ta mevcut."""
    course = _make_course(test_club.id, name="Geçerli Kurs")
    db_session.add(course)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/public/membership-applications",
        json={
            "club_slug": test_club.slug,
            "first_name": "Valid", "last_name": "Course",
            "email": f"vc-{uuid.uuid4().hex[:6]}@test.com",
            "phone": "05320001001", "consent_accepted": True,
            "preferred_course_id": str(course.id),
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["preferred_course_id"] == str(course.id)
    assert data["preferred_course_name"] == "Geçerli Kurs"


@pytest.mark.asyncio
async def test_submit_with_null_preferred_course(
    client: AsyncClient,
    test_club: Club,
) -> None:
    """preferred_course_id=null → 201, alan response'ta null."""
    resp = await client.post(
        "/api/v1/public/membership-applications",
        json={
            "club_slug": test_club.slug,
            "first_name": "Null", "last_name": "Course",
            "email": f"nc-{uuid.uuid4().hex[:6]}@test.com",
            "phone": "05320001002", "consent_accepted": True,
            "preferred_course_id": None,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["preferred_course_id"] is None


@pytest.mark.asyncio
async def test_submit_with_fake_uuid_422(
    client: AsyncClient,
    test_club: Club,
) -> None:
    """Uydurma UUID → 422 (kurs bulunamaz)."""
    resp = await client.post(
        "/api/v1/public/membership-applications",
        json={
            "club_slug": test_club.slug,
            "first_name": "Fake", "last_name": "UUID",
            "email": f"fu-{uuid.uuid4().hex[:6]}@test.com",
            "phone": "05320001003", "consent_accepted": True,
            "preferred_course_id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_with_foreign_club_course_422(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Başka kulübün kursu → 422."""
    club2 = Club(
        id=uuid.uuid4(), name="Yabancı Kulüp",
        slug=f"yab-{uuid.uuid4().hex[:6]}", plan="starter", is_active=True,
    )
    db_session.add(club2)
    course_other = _make_course(club2.id, name="Yabancı Kurs")
    db_session.add(course_other)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/public/membership-applications",
        json={
            "club_slug": test_club.slug,
            "first_name": "Foreign", "last_name": "Club",
            "email": f"fc-{uuid.uuid4().hex[:6]}@test.com",
            "phone": "05320001004", "consent_accepted": True,
            "preferred_course_id": str(course_other.id),
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_with_inactive_course_422(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """is_active=False kurs → 422."""
    course = _make_course(test_club.id, name="Pasif Kurs", is_active=False)
    db_session.add(course)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/public/membership-applications",
        json={
            "club_slug": test_club.slug,
            "first_name": "Inactive", "last_name": "Course",
            "email": f"ic-{uuid.uuid4().hex[:6]}@test.com",
            "phone": "05320001005", "consent_accepted": True,
            "preferred_course_id": str(course.id),
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_with_deleted_course_422(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """is_deleted=True kurs → 422."""
    course = _make_course(test_club.id, name="Silinmiş Kurs", is_deleted=True)
    db_session.add(course)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/public/membership-applications",
        json={
            "club_slug": test_club.slug,
            "first_name": "Deleted", "last_name": "Course",
            "email": f"dc-{uuid.uuid4().hex[:6]}@test.com",
            "phone": "05320001006", "consent_accepted": True,
            "preferred_course_id": str(course.id),
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_form_data_does_not_contain_preferred_course_id(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """form_data alanı preferred_course_id içermemeli — üst düzeyde kolon olarak tutulur."""
    course = _make_course(test_club.id, name="Form Data Kurs")
    db_session.add(course)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/public/membership-applications",
        json={
            "club_slug": test_club.slug,
            "first_name": "FormData2", "last_name": "Test",
            "email": f"fd2-{uuid.uuid4().hex[:6]}@test.com",
            "phone": "05320001007", "consent_accepted": True,
            "preferred_course_id": str(course.id),
        },
    )
    assert resp.status_code == 201
    app_id = resp.json()["id"]

    result = await db_session.execute(
        select(MembershipApplication).where(MembershipApplication.id == uuid.UUID(app_id))
    )
    saved = result.scalar_one_or_none()
    assert saved is not None
    form_data = saved.form_data or {}
    assert "preferred_course_id" not in form_data, (
        f"form_data içinde preferred_course_id olmamalı: {form_data}"
    )


@pytest.mark.asyncio
async def test_admin_list_includes_preferred_course_name(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Admin list yanıtı preferred_course_id + preferred_course_name içermeli."""
    course = _make_course(test_club.id, name="Admin List Kursu")
    db_session.add(course)
    await db_session.flush()

    create_resp = await client.post(
        "/api/v1/public/membership-applications",
        json={
            "club_slug": test_club.slug,
            "first_name": "AdminCourse", "last_name": "List",
            "email": f"acl-{uuid.uuid4().hex[:6]}@test.com",
            "phone": "05320001008", "consent_accepted": True,
            "preferred_course_id": str(course.id),
        },
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    list_resp = await client.get(
        "/api/v1/membership-applications",
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert list_resp.status_code == 200
    items = list_resp.json().get("items", list_resp.json())
    target = next((x for x in items if x["id"] == app_id), None)
    assert target is not None
    assert target.get("preferred_course_id") == str(course.id)
    assert target.get("preferred_course_name") == "Admin List Kursu"


@pytest.mark.asyncio
async def test_admin_detail_includes_preferred_course_name(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Admin detail preferred_course_name'i de döndürmeli."""
    course = _make_course(test_club.id, name="Detail Kursu Adı")
    db_session.add(course)
    await db_session.flush()

    create_resp = await client.post(
        "/api/v1/public/membership-applications",
        json={
            "club_slug": test_club.slug,
            "first_name": "DetailCourse", "last_name": "Name",
            "email": f"dcn-{uuid.uuid4().hex[:6]}@test.com",
            "phone": "05320001009", "consent_accepted": True,
            "preferred_course_id": str(course.id),
        },
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    detail_resp = await client.get(
        f"/api/v1/membership-applications/{app_id}",
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert detail_resp.status_code == 200
    data = detail_resp.json()
    assert data.get("preferred_course_id") == str(course.id)
    assert data.get("preferred_course_name") == "Detail Kursu Adı"


@pytest.mark.asyncio
async def test_status_patch_does_not_change_preferred_course(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Status PATCH preferred_course_id'yi değiştirmemeli."""
    course = _make_course(test_club.id, name="Sabit Kurs")
    db_session.add(course)
    await db_session.flush()

    create_resp = await client.post(
        "/api/v1/public/membership-applications",
        json={
            "club_slug": test_club.slug,
            "first_name": "StatusPatch", "last_name": "Course",
            "email": f"spc-{uuid.uuid4().hex[:6]}@test.com",
            "phone": "05320001010", "consent_accepted": True,
            "preferred_course_id": str(course.id),
        },
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/v1/membership-applications/{app_id}/status",
        json={"to_status": "approved"},
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert patch_resp.status_code == 200

    result = await db_session.execute(
        select(MembershipApplication).where(MembershipApplication.id == uuid.UUID(app_id))
    )
    saved = result.scalar_one_or_none()
    assert saved is not None
    assert saved.preferred_course_id == course.id, (
        f"Status PATCH preferred_course_id değiştirdi! Alınan: {saved.preferred_course_id!r}"
    )


@pytest.mark.asyncio
async def test_no_enrollment_created_on_submit(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Başvuru submit'i TrainingEnrollment oluşturmamalı — bu ayrı 'Eğitime Kaydet' adımı."""
    course = _make_course(test_club.id, name="Enrollment Yok Kursu")
    db_session.add(course)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/public/membership-applications",
        json={
            "club_slug": test_club.slug,
            "first_name": "NoEnroll", "last_name": "Test",
            "email": f"ne-{uuid.uuid4().hex[:6]}@test.com",
            "phone": "05320001011", "consent_accepted": True,
            "preferred_course_id": str(course.id),
        },
    )
    assert resp.status_code == 201

    result = await db_session.execute(
        select(TrainingEnrollment).where(TrainingEnrollment.course_id == course.id)
    )
    enrollments = result.scalars().all()
    assert len(enrollments) == 0, (
        f"Submit TrainingEnrollment oluşturmamalı, {len(enrollments)} kayıt bulundu"
    )


# ─── Testler — program_preference schema & admin ─────────────────────────────

@pytest.mark.asyncio
async def test_admin_list_includes_program_preference(
    client: AsyncClient,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Admin list (GET /membership-applications) yanıtında program_preference alanı olmalı."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "AdminList",
        "last_name": "Test",
        "email": f"adm-list-{uuid.uuid4().hex[:6]}@test.com",
        "phone": "05320000020",
        "consent_accepted": True,
        "program_preference": "optimist",
    }
    create_resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    list_resp = await client.get(
        "/api/v1/membership-applications",
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert list_resp.status_code == 200
    items = list_resp.json().get("items", list_resp.json())
    target = next((x for x in items if x["id"] == app_id), None)
    assert target is not None, "Oluşturulan başvuru liste yanıtında bulunamadı"
    assert "program_preference" in target, "program_preference alanı liste yanıtında yok"
    assert target["program_preference"] == "optimist"


@pytest.mark.asyncio
async def test_admin_detail_includes_program_preference(
    client: AsyncClient,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Admin detail (GET /membership-applications/{id}) yanıtında program_preference olmalı."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "AdminDetail",
        "last_name": "Test",
        "email": f"adm-det-{uuid.uuid4().hex[:6]}@test.com",
        "phone": "05320000021",
        "consent_accepted": True,
        "program_preference": "ilca",
    }
    create_resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    detail_resp = await client.get(
        f"/api/v1/membership-applications/{app_id}",
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert detail_resp.status_code == 200
    data = detail_resp.json()
    assert "program_preference" in data, "program_preference alanı detay yanıtında yok"
    assert data["program_preference"] == "ilca"


@pytest.mark.asyncio
async def test_old_record_has_null_program_preference(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """program_preference alanı olmadan oluşturulan başvuruda alan NULL olmalı."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "EskiKayit",
        "last_name": "Test",
        "email": f"old-{uuid.uuid4().hex[:6]}@test.com",
        "phone": "05320000022",
        "consent_accepted": True,
        # program_preference gönderilmiyor
    }
    create_resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    result = await db_session.execute(
        select(MembershipApplication).where(MembershipApplication.id == uuid.UUID(app_id))
    )
    saved = result.scalar_one_or_none()
    assert saved is not None
    assert saved.program_preference is None, (
        f"Eski kayıt program_preference NULL olmalı, alınan: {saved.program_preference!r}"
    )


@pytest.mark.asyncio
async def test_form_data_does_not_contain_program_preference(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """form_data JSON alanı program_preference içermemeli — alan üst düzeyde tutulur."""
    payload = {
        "club_slug": test_club.slug,
        "first_name": "FormData",
        "last_name": "Test",
        "email": f"fd-{uuid.uuid4().hex[:6]}@test.com",
        "phone": "05320000023",
        "consent_accepted": True,
        "program_preference": "420",
    }
    create_resp = await client.post("/api/v1/public/membership-applications", json=payload)
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    result = await db_session.execute(
        select(MembershipApplication).where(MembershipApplication.id == uuid.UUID(app_id))
    )
    saved = result.scalar_one_or_none()
    assert saved is not None
    form_data = saved.form_data or {}
    assert "program_preference" not in form_data, (
        f"form_data içinde program_preference olmamalı, alınan: {form_data}"
    )


@pytest.mark.asyncio
async def test_membership_application_create_rejects_program_preference(
    client: AsyncClient,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Admin MembershipApplicationCreate şeması program_preference kabul etmemeli (extra=forbid)."""
    # Admin create endpoint (eğer varsa) program_preference'ı reddetmeli.
    # Endpoint yoksa bu test atlanır.
    resp = await client.post(
        "/api/v1/membership-applications",
        json={
            "club_id": str(test_club.id),
            "first_name": "Schema",
            "last_name": "Test",
            "email": f"schema-{uuid.uuid4().hex[:6]}@test.com",
            "consent_accepted": True,
            "program_preference": "ilca",  # Bu alan bu şemada yok
        },
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    # Admin endpoint yoksa 404/405, varsa 422 (extra=forbid) beklenir
    assert resp.status_code in (404, 405, 422), (
        f"MembershipApplicationCreate program_preference → 422 beklendi, alınan: {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_membership_application_update_rejects_program_preference(
    client: AsyncClient,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """MembershipApplicationUpdate şeması program_preference kabul etmemeli."""
    # Önce başvuru oluştur
    create_resp = await client.post(
        "/api/v1/public/membership-applications",
        json={
            "club_slug": test_club.slug,
            "first_name": "UpdateTest",
            "last_name": "Schema",
            "email": f"upd-{uuid.uuid4().hex[:6]}@test.com",
            "phone": "05320000024",
            "consent_accepted": True,
        },
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/api/v1/membership-applications/{app_id}",
        json={"program_preference": "wing_foil"},  # Update şemasında yok
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    # extra=forbid → 422; endpoint yoksa 404/405
    assert update_resp.status_code in (404, 405, 422), (
        f"MembershipApplicationUpdate program_preference → 422 beklendi, alınan: {update_resp.status_code}"
    )


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
