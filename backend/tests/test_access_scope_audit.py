"""Liste, detay ve ilişki uçlarında nesne bazlı erişim regresyonları."""

from datetime import date, timedelta

import pytest

from app.models.payment import Payment
from app.models.person_guardian import PersonGuardian
from tests.test_antrenor_scope import (
    _assign_course_instructor,
    _course,
    _enroll,
    _h,
    _person,
    _token,
    _user,
)

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("role", ["sporcu", "veli", "antrenor", "basantrenor"])
async def test_athlete_read_scope(client, db_session, test_club, role):
    own = await _person(db_session, test_club, role_codes=["sporcu"])
    other = await _person(db_session, test_club, role_codes=["sporcu"])
    user_person = own if role == "sporcu" else await _person(db_session, test_club)
    user = await _user(db_session, test_club, role=role, person=user_person)
    if role == "veli":
        db_session.add(
            PersonGuardian(
                club_id=test_club.id,
                athlete_person_id=own.id,
                guardian_person_id=user_person.id,
            )
        )
    elif role in {"antrenor", "basantrenor"}:
        course = await _course(db_session, test_club)
        await _assign_course_instructor(db_session, test_club, course, user_person)
        await _enroll(db_session, test_club, course, own)
    await db_session.flush()
    h = _h(_token(user, test_club))
    listing = await client.get("/api/v1/athletes", headers=h)
    assert listing.status_code == 200
    assert {x["person_id"] for x in listing.json()["items"]} == {str(own.id)}
    alerts = await client.get("/api/v1/athletes/alerts", headers=h)
    assert alerts.status_code == 200
    assert {x["person_id"] for x in alerts.json()} == {str(own.id)}
    assert (
        await client.get(f"/api/v1/athletes/{own.id}", headers=h)
    ).status_code == 200
    assert (
        await client.get(f"/api/v1/athletes/{other.id}", headers=h)
    ).status_code == 403


async def test_revoked_guardian_loses_reads(client, db_session, test_club):
    guardian = await _person(db_session, test_club)
    athlete = await _person(db_session, test_club, role_codes=["sporcu"])
    user = await _user(db_session, test_club, role="veli", person=guardian)
    link = PersonGuardian(
        club_id=test_club.id,
        guardian_person_id=guardian.id,
        athlete_person_id=athlete.id,
        is_active=True,
    )
    payment = Payment(
        club_id=test_club.id,
        person_id=athlete.id,
        amount=100,
        status="pending",
        due_date=date.today() - timedelta(days=1),
    )
    db_session.add_all([link, payment])
    course = await _course(db_session, test_club)
    await _enroll(db_session, test_club, course, athlete)
    await db_session.flush()
    h = _h(_token(user, test_club))
    payment_url = f"/api/v1/payments/{payment.id}"
    course_url = f"/api/v1/trainings/{course.id}"
    assert (await client.get(payment_url, headers=h)).status_code == 200
    assert (await client.get(course_url, headers=h)).status_code == 200
    link.is_active = False
    await db_session.flush()
    assert (await client.get(payment_url, headers=h)).status_code == 403
    assert (await client.get(course_url, headers=h)).status_code == 403
    listing = await client.get("/api/v1/payments", headers=h)
    assert listing.status_code == 200
    assert listing.json()["items"] == []
    assert (await client.get("/api/v1/payments/overdue", headers=h)).json() == []
    assert (await client.get("/api/v1/trainings", headers=h)).json()["items"] == []
    assert (
        await client.get(f"/api/v1/athletes/{athlete.id}", headers=h)
    ).status_code == 403


@pytest.mark.parametrize("suffix", ["guardians", "athletes"])
async def test_coach_cannot_read_unassigned_relationships(
    client, db_session, test_club, suffix
):
    coach = await _person(db_session, test_club)
    user = await _user(db_session, test_club, person=coach)
    outside = await _person(db_session, test_club)
    h = _h(_token(user, test_club))
    assert (
        await client.get(f"/api/v1/persons/{outside.id}/{suffix}", headers=h)
    ).status_code == 403


@pytest.mark.parametrize("role", ["veli", "sporcu", "uye", "misafir", "antrenor"])
async def test_dashboard_does_not_leak_club_records(
    client, db_session, test_club, role
):
    from app.models.audit import AuditLog
    from tests.test_antrenor_scope import _session

    person = await _person(db_session, test_club)
    user = await _user(db_session, test_club, role=role, person=person)
    outsider = await _person(db_session, test_club, role_codes=["sporcu"])
    course = await _course(db_session, test_club, name="Kapsam dışı kurs")
    await _session(db_session, test_club, course)
    db_session.add_all(
        [
            Payment(
                club_id=test_club.id,
                person_id=outsider.id,
                amount=98765,
                status="pending",
                due_date=date.today() - timedelta(days=1),
            ),
            AuditLog(
                club_id=test_club.id,
                action="payment_created",
                resource_type="payment",
                resource_id="private-record",
            ),
        ]
    )
    await db_session.flush()
    resp = await client.get(
        "/api/v1/dashboard/stats", headers=_h(_token(user, test_club))
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["vadesi_gecen_odeme_toplami"] == 0
    assert data["vadesi_gecen_odeme"] == 0
    assert data["son_aktiviteler"] == []
    assert data["bugunun_oturumlari"] == []
    assert data["aktif_kurs_sayisi"] == 0
    assert data["aktif_sporcu"] == 0


@pytest.mark.parametrize("role", ["veli", "sporcu", "antrenor"])
async def test_dashboard_preserves_allowed_records(client, db_session, test_club, role):
    from tests.test_antrenor_scope import _session

    athlete = await _person(db_session, test_club, role_codes=["sporcu"])
    actor = athlete if role == "sporcu" else await _person(db_session, test_club)
    user = await _user(db_session, test_club, role=role, person=actor)
    course = await _course(db_session, test_club)
    session = await _session(db_session, test_club, course)
    await _enroll(db_session, test_club, course, athlete)
    if role == "veli":
        db_session.add(
            PersonGuardian(
                club_id=test_club.id,
                guardian_person_id=actor.id,
                athlete_person_id=athlete.id,
            )
        )
    elif role == "antrenor":
        await _assign_course_instructor(db_session, test_club, course, actor)
    db_session.add(
        Payment(
            club_id=test_club.id,
            person_id=athlete.id,
            amount=100,
            status="pending",
            due_date=date.today() - timedelta(days=1),
        )
    )
    await db_session.flush()
    resp = await client.get(
        "/api/v1/dashboard/stats", headers=_h(_token(user, test_club))
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["aktif_sporcu"] == 1
    assert data["aktif_kurs_sayisi"] == 1
    assert data["bugunun_oturumlari"][0]["session_id"] == str(session.id)
    assert data["vadesi_gecen_odeme_toplami"] == (100 if role == "veli" else 0)


@pytest.mark.parametrize("role", ["veli", "sporcu"])
async def test_unlinked_account_sees_no_athletes(client, db_session, test_club, role):
    user = await _user(db_session, test_club, role=role)
    athlete = await _person(db_session, test_club, role_codes=["sporcu"])
    h = _h(_token(user, test_club))
    resp = await client.get("/api/v1/athletes", headers=h)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert (
        await client.get(f"/api/v1/athletes/{athlete.id}", headers=h)
    ).status_code == 403


@pytest.mark.parametrize("role", ["uye", "misafir"])
async def test_member_and_guest_cannot_read_athlete_records(
    client, db_session, test_club, role
):
    athlete = await _person(db_session, test_club, role_codes=["sporcu"])
    user = await _user(db_session, test_club, role=role, person=athlete)
    h = _h(_token(user, test_club))
    for path in [
        "/api/v1/athletes",
        "/api/v1/athletes/alerts",
        f"/api/v1/athletes/{athlete.id}",
    ]:
        assert (await client.get(path, headers=h)).status_code == 403
