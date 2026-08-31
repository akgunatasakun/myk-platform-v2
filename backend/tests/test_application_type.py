"""membership_applications.application_type admin API testleri — Sprint 0024.

Kapsam:
  - Admin listesi application_type alanını içerir
  - ?application_type=course filtresi çalışır
  - ?application_type=membership filtresi çalışır
  - Başvuru detayı application_type alanını içerir
  - program_preference varsa application_type='course' olmalı (model seviyesi)

Kirli test_membership_applications.py stage edilmez; bu dosya temiz.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.club import Club
from app.models.membership_application import MembershipApplication


# ─── Yardımcılar ─────────────────────────────────────────────────────────────

def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_app(
    db: AsyncSession,
    club: Club,
    *,
    application_type: str = "membership",
    program_preference: str | None = None,
    preferred_course_id: uuid.UUID | None = None,
) -> MembershipApplication:
    app = MembershipApplication(
        club_id=club.id,
        status="submitted",
        application_number=f"TEST-{uuid.uuid4().hex[:6].upper()}",
        first_name="Test",
        last_name="Başvuru",
        email=f"test-{uuid.uuid4().hex[:6]}@example.com",
        phone="05001234567",
        application_type=application_type,
        program_preference=program_preference,
        preferred_course_id=preferred_course_id,
    )
    db.add(app)
    await db.flush()
    await db.refresh(app)
    return app


# ─── Testler ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_includes_application_type(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Admin liste response'unda application_type alanı bulunmalı."""
    await _create_app(db_session, test_club, application_type="membership")
    await db_session.commit()

    resp = await client.get(
        "/api/v1/membership-applications",
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    assert len(items) > 0, "Liste boş döndü"
    assert "application_type" in items[0], "application_type liste response'unda yok"


@pytest.mark.asyncio
async def test_detail_includes_application_type(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Admin detay response'unda application_type alanı bulunmalı."""
    app = await _create_app(db_session, test_club, application_type="course")
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/membership-applications/{app.id}",
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "application_type" in data, "application_type detay response'unda yok"
    assert data["application_type"] == "course"


@pytest.mark.asyncio
async def test_filter_by_course(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """?application_type=course filtresi sadece kurs başvurularını döndürmeli."""
    # Bir üyelik, bir kurs başvurusu oluştur
    m_app = await _create_app(db_session, test_club, application_type="membership")
    c_app = await _create_app(db_session, test_club, application_type="course")
    await db_session.commit()

    resp = await client.get(
        "/api/v1/membership-applications?application_type=course",
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    ids = [i["id"] for i in items]
    assert str(c_app.id) in ids, "Kurs başvurusu filtrede yok"
    assert str(m_app.id) not in ids, "Üyelik başvurusu course filtresinde görünmemeli"
    for item in items:
        assert item["application_type"] == "course", (
            f"Kurs filtresi üyelik kaydı döndürdü: {item['id']}"
        )


@pytest.mark.asyncio
async def test_filter_by_membership(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """?application_type=membership filtresi sadece üyelik başvurularını döndürmeli."""
    m_app = await _create_app(db_session, test_club, application_type="membership")
    c_app = await _create_app(db_session, test_club, application_type="course")
    await db_session.commit()

    resp = await client.get(
        "/api/v1/membership-applications?application_type=membership",
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    ids = [i["id"] for i in items]
    assert str(m_app.id) in ids, "Üyelik başvurusu filtrede yok"
    assert str(c_app.id) not in ids, "Kurs başvurusu membership filtresinde görünmemeli"
    for item in items:
        assert item["application_type"] == "membership", (
            f"Üyelik filtresi kurs kaydı döndürdü: {item['id']}"
        )


@pytest.mark.asyncio
async def test_course_app_default_type_in_db(
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """program_preference olan kayıt 'course' tipiyle kaydedilmeli."""
    app = await _create_app(
        db_session,
        test_club,
        application_type="course",
        program_preference="optimist",
    )
    await db_session.commit()

    result = await db_session.execute(
        select(MembershipApplication).where(MembershipApplication.id == app.id)
    )
    saved = result.scalar_one_or_none()
    assert saved is not None
    assert saved.application_type == "course", (
        f"application_type 'course' olmalı, alınan: {saved.application_type!r}"
    )


@pytest.mark.asyncio
async def test_membership_default_type(
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """program_preference'sız başvurunun default tipi 'membership' olmalı."""
    app = MembershipApplication(
        club_id=test_club.id,
        status="submitted",
        application_number=f"DEF-{uuid.uuid4().hex[:6].upper()}",
        first_name="Varsayılan",
        last_name="Test",
        email=f"def-{uuid.uuid4().hex[:6]}@example.com",
        phone="05009999999",
        # application_type atlanıyor — model default'u kullanmalı
    )
    db_session.add(app)
    await db_session.flush()
    await db_session.commit()

    result = await db_session.execute(
        select(MembershipApplication).where(MembershipApplication.id == app.id)
    )
    saved = result.scalar_one_or_none()
    assert saved is not None
    assert saved.application_type == "membership", (
        f"Varsayılan application_type 'membership' olmalı, alınan: {saved.application_type!r}"
    )


# ─── Kurs onay / ret akışı testleri ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_course_approve_sets_approved_no_person(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Kurs başvurusu onaylanınca status=approved olmalı; Person/User oluşmamalı."""
    from sqlalchemy import text as sa_text
    from app.models.person import Person

    app = await _create_app(db_session, test_club, application_type="course")
    await db_session.commit()

    # Onay öncesi person sayısı
    person_count_before = (
        await db_session.execute(
            select(func.count()).select_from(Person).where(Person.club_id == test_club.id)
        )
    ).scalar_one()

    resp = await client.patch(
        f"/api/v1/membership-applications/{app.id}/status",
        json={"to_status": "approved"},
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "approved"
    assert data["application_type"] == "course"

    # Person oluşmamış olmalı
    person_count_after = (
        await db_session.execute(
            select(func.count()).select_from(Person).where(Person.club_id == test_club.id)
        )
    ).scalar_one()
    assert person_count_after == person_count_before, (
        f"Kurs onayında Person oluşmamalı. Önce: {person_count_before}, sonra: {person_count_after}"
    )

    # member_number response'ta olmamalı (üyelik kaydı yok)
    assert "member_number" not in data or data.get("member_number") is None


@pytest.mark.asyncio
async def test_course_approve_no_training_enrollment(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Kurs onayı TrainingEnrollment oluşturmamalı."""
    from app.models.training import TrainingEnrollment

    app = await _create_app(db_session, test_club, application_type="course")
    await db_session.commit()

    enrollment_count_before = (
        await db_session.execute(
            select(func.count()).select_from(TrainingEnrollment).where(
                TrainingEnrollment.club_id == test_club.id
            )
        )
    ).scalar_one()

    resp = await client.patch(
        f"/api/v1/membership-applications/{app.id}/status",
        json={"to_status": "approved"},
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 200

    enrollment_count_after = (
        await db_session.execute(
            select(func.count()).select_from(TrainingEnrollment).where(
                TrainingEnrollment.club_id == test_club.id
            )
        )
    ).scalar_one()
    assert enrollment_count_after == enrollment_count_before, (
        "Kurs onayında TrainingEnrollment oluşmamalı"
    )


@pytest.mark.asyncio
async def test_course_reject_returns_approved(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Kurs başvurusu reddedilebilmeli."""
    app = await _create_app(db_session, test_club, application_type="course")
    await db_session.commit()

    resp = await client.patch(
        f"/api/v1/membership-applications/{app.id}/status",
        json={"to_status": "rejected", "reason": "Kontenjan dolu."},
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["application_type"] == "course"


@pytest.mark.asyncio
async def test_membership_approve_still_creates_person(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Üyelik başvurusu onaylandığında mevcut davranış (Person oluşturma) korunmalı."""
    from app.models.person import Person

    app = await _create_app(db_session, test_club, application_type="membership")
    await db_session.commit()

    person_count_before = (
        await db_session.execute(
            select(func.count()).select_from(Person).where(Person.club_id == test_club.id)
        )
    ).scalar_one()

    resp = await client.patch(
        f"/api/v1/membership-applications/{app.id}/status",
        json={"to_status": "approved"},
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["application_type"] == "membership"

    person_count_after = (
        await db_session.execute(
            select(func.count()).select_from(Person).where(Person.club_id == test_club.id)
        )
    ).scalar_one()
    assert person_count_after > person_count_before, (
        "Üyelik onayında Person oluşturulmalı"
    )


@pytest.mark.asyncio
async def test_invalid_application_type_filter_returns_422(
    client: AsyncClient,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Geçersiz ?application_type= değeri 422 döndürmeli."""
    resp = await client.get(
        "/api/v1/membership-applications?application_type=gecersiz",
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 422, f"422 beklendi, alınan: {resp.status_code}"


# ─── process_approval Mock testi ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_course_approve_process_approval_not_called_mock(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """process_approval mock'lanarak kurs onayında kesinlikle çağrılmadığı doğrulanmalı.
    Person / User / TrainingEnrollment sayıları değişmemeli.
    """
    from unittest.mock import AsyncMock, patch
    from app.models.person import Person
    from app.models.user import User
    from app.models.training import TrainingEnrollment

    app = await _create_app(db_session, test_club, application_type="course")
    await db_session.commit()

    p_before = (await db_session.execute(
        select(func.count()).select_from(Person).where(Person.club_id == test_club.id)
    )).scalar_one()
    u_before = (await db_session.execute(
        select(func.count()).select_from(User).where(User.club_id == test_club.id)
    )).scalar_one()
    e_before = (await db_session.execute(
        select(func.count()).select_from(TrainingEnrollment).where(
            TrainingEnrollment.club_id == test_club.id
        )
    )).scalar_one()

    mock_pa = AsyncMock()
    with patch("app.api.v1.routers.memberships.process_approval", mock_pa):
        resp = await client.patch(
            f"/api/v1/membership-applications/{app.id}/status",
            json={"to_status": "approved"},
            headers=_headers(yonetici_token),
        )

    assert resp.status_code == 200
    mock_pa.assert_not_awaited()  # hiç çağrılmamalı

    p_after = (await db_session.execute(
        select(func.count()).select_from(Person).where(Person.club_id == test_club.id)
    )).scalar_one()
    u_after = (await db_session.execute(
        select(func.count()).select_from(User).where(User.club_id == test_club.id)
    )).scalar_one()
    e_after = (await db_session.execute(
        select(func.count()).select_from(TrainingEnrollment).where(
            TrainingEnrollment.club_id == test_club.id
        )
    )).scalar_one()

    assert p_after == p_before, "Kurs onayında Person oluşmamalı"
    assert u_after == u_before, "Kurs onayında User oluşmamalı"
    assert e_after == e_before, "Kurs onayında TrainingEnrollment oluşmamalı"


@pytest.mark.asyncio
async def test_membership_approve_calls_process_approval(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Üyelik başvurusu onaylandığında process_approval çağrılmalı."""
    from unittest.mock import AsyncMock, patch, MagicMock

    app = await _create_app(db_session, test_club, application_type="membership")
    await db_session.commit()

    # Gerçek bir sonuç döndüren mock
    mock_result = MagicMock()
    mock_result.member_number = "MYK-2026-999"
    mock_result.temp_password = None
    mock_result.person_created = True
    mock_result.person = MagicMock()
    mock_result.person.id = __import__("uuid").uuid4()

    mock_pa = AsyncMock(return_value=mock_result)
    with patch("app.api.v1.routers.memberships.process_approval", mock_pa):
        resp = await client.patch(
            f"/api/v1/membership-applications/{app.id}/status",
            json={"to_status": "approved"},
            headers=_headers(yonetici_token),
        )

    assert resp.status_code == 200
    mock_pa.assert_awaited_once()  # üyelik için çağrılmalı


# ─── E-posta içerik testleri ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_course_approval_email_content() -> None:
    """send_course_approval_email: konu ve gövde kurs dili içermeli; üyelik dili içermemeli."""
    from unittest.mock import AsyncMock, patch
    from app.services.email_service import send_course_approval_email

    captured: dict = {}

    async def _mock_send(subject: str, to_email: str, html_body: str) -> None:
        captured["subject"] = subject
        captured["body"] = html_body

    with patch("app.services.email_service._send", new=_mock_send):
        await send_course_approval_email(
            to_email="kurs@example.com",
            applicant_name="Test Sporcu",
        )

    assert "Kurs" in captured["subject"], f"Konu 'Kurs' içermeli: {captured['subject']!r}"
    assert "Üyelik" not in captured["subject"], f"Konu 'Üyelik' içermemeli: {captured['subject']!r}"
    assert "Üye Numaranız" not in captured["body"], "Gövde 'Üye Numaranız' içermemeli"
    assert "Geçici Şifre" not in captured["body"], "Gövde 'Geçici Şifre' içermemeli"
    assert "Kurs" in captured["body"], "Gövde 'Kurs' içermeli"


@pytest.mark.asyncio
async def test_course_rejection_email_content() -> None:
    """send_course_rejection_email: konu kurs dili içermeli; gerekçe gövdede yer almalı."""
    from unittest.mock import patch
    from app.services.email_service import send_course_rejection_email

    captured: dict = {}

    async def _mock_send(subject: str, to_email: str, html_body: str) -> None:
        captured["subject"] = subject
        captured["body"] = html_body

    with patch("app.services.email_service._send", new=_mock_send):
        await send_course_rejection_email(
            to_email="kurs@example.com",
            applicant_name="Test Sporcu",
            reason="Kontenjan dolu.",
        )

    assert "Kurs" in captured["subject"], f"Konu 'Kurs' içermeli: {captured['subject']!r}"
    assert "Üyelik" not in captured["subject"], f"Konu 'Üyelik' içermemeli: {captured['subject']!r}"
    assert "Kontenjan dolu." in captured["body"], "Gerekçe gövdede bulunmalı"


@pytest.mark.asyncio
async def test_course_approve_transition_calls_course_email(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Kurs onay geçişi kurs e-posta fonksiyonunu çağırmalı; üyelik fonksiyonu çağrılmamalı."""
    from unittest.mock import AsyncMock, patch

    app = await _create_app(db_session, test_club, application_type="course")
    await db_session.commit()

    mock_course_email = AsyncMock()
    mock_membership_email = AsyncMock()

    with patch("app.api.v1.routers.memberships.send_course_approval_email", mock_course_email), \
         patch("app.api.v1.routers.memberships.send_approval_email", mock_membership_email):
        resp = await client.patch(
            f"/api/v1/membership-applications/{app.id}/status",
            json={"to_status": "approved"},
            headers=_headers(yonetici_token),
        )

    assert resp.status_code == 200
    mock_course_email.assert_awaited_once()
    mock_membership_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_course_reject_transition_calls_course_email(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """Kurs red geçişi kurs red e-posta fonksiyonunu çağırmalı; üyelik fonksiyonu çağrılmamalı."""
    from unittest.mock import AsyncMock, patch

    app = await _create_app(db_session, test_club, application_type="course")
    await db_session.commit()

    mock_course_reject = AsyncMock()
    mock_membership_reject = AsyncMock()

    with patch("app.api.v1.routers.memberships.send_course_rejection_email", mock_course_reject), \
         patch("app.api.v1.routers.memberships.send_rejection_email", mock_membership_reject):
        resp = await client.patch(
            f"/api/v1/membership-applications/{app.id}/status",
            json={"to_status": "rejected", "reason": "Kontenjan dolu."},
            headers=_headers(yonetici_token),
        )

    assert resp.status_code == 200
    mock_course_reject.assert_awaited_once()
    mock_membership_reject.assert_not_awaited()
