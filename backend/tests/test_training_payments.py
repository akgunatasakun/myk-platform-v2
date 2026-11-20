"""Eğitim tahsilatı: açık eşleştirme, kısmi/tam ödeme ve erişim sınırları."""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.club import Club
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


async def _setup(db, club):
    person = await _person(db, club, role_codes=["sporcu"])
    course = await _course(db, club)
    course.fee = Decimal("1000")
    enrollment = await _enroll(db, club, course, person)
    await db.flush()
    return person, course, enrollment


async def _summary(client, course, headers):
    response = await client.get(
        f"/api/v1/trainings/{course.id}/participants", headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()[0]


async def test_course_attendance_payment_flow(client, db_session, test_club, test_user):
    h = _h(_token(test_user, test_club))
    person = await _person(db_session, test_club, role_codes=["sporcu"])
    other = await _person(db_session, test_club, role_codes=["sporcu"])
    course = await client.post(
        "/api/v1/trainings",
        headers=h,
        json={"name": "YTE D1 Test", "capacity": 1, "fee": "1000"},
    )
    assert course.status_code == 201
    cid = course.json()["id"]
    enrollment = await client.post(
        f"/api/v1/trainings/{cid}/participants",
        headers=h,
        json={"person_id": str(person.id)},
    )
    assert enrollment.status_code == 201
    eid = enrollment.json()["id"]
    assert enrollment.json()["balance"] == "1000.00"
    assert (
        await client.post(
            f"/api/v1/trainings/{cid}/participants",
            headers=h,
            json={"person_id": str(other.id)},
        )
    ).status_code == 409
    session = await client.post(
        f"/api/v1/trainings/{cid}/sessions",
        headers=h,
        json={"session_date": str(date.today())},
    )
    assert session.status_code == 201
    sid = session.json()["id"]
    assert (
        await client.put(
            f"/api/v1/trainings/{cid}/sessions/{sid}/attendance",
            headers=h,
            json={"records": [{"person_id": str(person.id), "status": "var"}]},
        )
    ).status_code == 200
    payment = await client.post(
        "/api/v1/payments",
        headers=h,
        json={
            "person_id": str(person.id),
            "training_enrollment_id": eid,
            "amount": "1000",
            "status": "paid",
        },
    )
    assert payment.status_code == 201, payment.text
    summary = (
        await client.get(f"/api/v1/trainings/{cid}/participants", headers=h)
    ).json()[0]
    assert summary["payment_status"] == "paid"
    assert Decimal(summary["paid_amount"]) == 1000
    assert Decimal(summary["balance"]) == 0


async def test_partial_paid_pending_update_delete_recomputes(
    client, db_session, test_club, test_user
):
    person, course, enr = await _setup(db_session, test_club)
    h = _h(_token(test_user, test_club))
    assert (await _summary(client, course, h))["payment_status"] == "unlinked"

    async def pay(amount, status):
        r = await client.post(
            "/api/v1/payments",
            headers=h,
            json={
                "person_id": str(person.id),
                "training_enrollment_id": str(enr.id),
                "amount": str(amount),
                "status": status,
            },
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]

    await pay(400, "paid")
    summary = await _summary(client, course, h)
    assert summary["payment_status"] == "partial"
    assert Decimal(summary["balance"]) == 600
    pending_id = await pay(600, "pending")
    assert Decimal((await _summary(client, course, h))["balance"]) == 600
    assert (
        await client.put(
            f"/api/v1/payments/{pending_id}", headers=h, json={"status": "paid"}
        )
    ).status_code == 200
    assert (await _summary(client, course, h))["payment_status"] == "paid"
    assert (
        await client.delete(f"/api/v1/payments/{pending_id}", headers=h)
    ).status_code == 204
    assert (await _summary(client, course, h))["payment_status"] == "partial"


async def test_existing_payment_link_unlink_reassign(
    client, db_session, test_club, test_user
):
    person, course, enr = await _setup(db_session, test_club)
    course2 = await _course(db_session, test_club)
    course2.fee = Decimal("1000")
    enr2 = await _enroll(db_session, test_club, course2, person)
    p = Payment(club_id=test_club.id, person_id=person.id, amount=1000, status="paid")
    db_session.add(p)
    await db_session.flush()
    h = _h(_token(test_user, test_club))
    assert (await _summary(client, course, h))["payment_status"] == "unlinked"
    for target in [enr.id, enr2.id, None]:
        r = await client.put(
            f"/api/v1/payments/{p.id}",
            headers=h,
            json={"training_enrollment_id": str(target) if target else None},
        )
        assert r.status_code == 200, r.text
        assert (await _summary(client, course, h))["payment_status"] == (
            "paid" if target == enr.id else "unlinked"
        )
        assert (await _summary(client, course2, h))["payment_status"] == (
            "paid" if target == enr2.id else "unlinked"
        )


@pytest.mark.parametrize(
    "invalid", ["other_person", "foreign_club", "cancelled", "missing_person"]
)
async def test_invalid_link_rejected(client, db_session, test_club, test_user, invalid):
    person, course, enr = await _setup(db_session, test_club)
    pid = person.id
    if invalid == "other_person":
        pid = (await _person(db_session, test_club)).id
    elif invalid == "foreign_club":
        other_club = Club(id=uuid.uuid4(), slug=uuid.uuid4().hex, name="Başka Kulüp")
        db_session.add(other_club)
        await db_session.flush()
        _, _, enr = await _setup(db_session, other_club)
    elif invalid == "cancelled":
        enr.status = "cancelled"
    else:
        pid = None
    await db_session.flush()
    r = await client.post(
        "/api/v1/payments",
        headers=_h(_token(test_user, test_club)),
        json={
            "person_id": str(pid) if pid else None,
            "training_enrollment_id": str(enr.id),
            "amount": "1000",
        },
    )
    assert r.status_code == {"foreign_club": 404, "cancelled": 409}.get(invalid, 422), (
        r.text
    )


@pytest.mark.parametrize(
    "role", ["veli", "sporcu", "antrenor", "basantrenor", "uye", "misafir", "personel"]
)
async def test_link_options_and_writes_require_financial_permission(
    client, db_session, test_club, role
):
    person, _, enr = await _setup(db_session, test_club)
    user = await _user(db_session, test_club, role=role, person=person)
    h = _h(_token(user, test_club))
    assert (
        await client.get(
            "/api/v1/payments/training-enrollments",
            params={"person_id": str(person.id)},
            headers=h,
        )
    ).status_code == 403
    assert (
        await client.post(
            "/api/v1/payments",
            headers=h,
            json={
                "person_id": str(person.id),
                "training_enrollment_id": str(enr.id),
                "amount": "1000",
            },
        )
    ).status_code == 403


async def test_accountant_options_and_coach_redaction(client, db_session, test_club):
    person, course, enr = await _setup(db_session, test_club)
    coach = await _person(db_session, test_club)
    coach_user = await _user(db_session, test_club, role="antrenor", person=coach)
    await _assign_course_instructor(db_session, test_club, course, coach)
    accountant = await _user(db_session, test_club, role="muhasebe")
    p = Payment(
        club_id=test_club.id,
        person_id=person.id,
        training_enrollment_id=enr.id,
        amount=1000,
        status="paid",
    )
    db_session.add(p)
    await db_session.flush()
    r = await client.get(
        "/api/v1/payments/training-enrollments",
        params={"person_id": str(person.id)},
        headers=_h(_token(accountant, test_club)),
    )
    assert r.status_code == 200
    assert [o["id"] for o in r.json()] == [str(enr.id)]
    data = await _summary(client, course, _h(_token(coach_user, test_club)))
    assert data["payment_status"] == "restricted"
    assert data["paid_amount"] is None and data["balance"] is None


async def test_guardian_summary_stays_own_and_zero_fee(client, db_session, test_club):
    person, course, enr = await _setup(db_session, test_club)
    guardian = await _person(db_session, test_club)
    user = await _user(db_session, test_club, role="veli", person=guardian)
    outsider = await _person(db_session, test_club)
    await _enroll(db_session, test_club, course, outsider)
    db_session.add(
        PersonGuardian(
            club_id=test_club.id,
            guardian_person_id=guardian.id,
            athlete_person_id=person.id,
        )
    )
    course.fee = Decimal("0")
    await db_session.flush()
    r = await client.get(
        f"/api/v1/trainings/{course.id}/participants",
        headers=_h(_token(user, test_club)),
    )
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["id"] == str(enr.id)
    assert r.json()[0]["payment_status"] == "not_required"


async def test_update_rejects_other_person_and_preserves_cancelled_link(
    client, db_session, test_club, test_user
):
    person, _, enr = await _setup(db_session, test_club)
    other = await _person(db_session, test_club)
    payment = Payment(
        club_id=test_club.id, person_id=other.id, amount=1000, status="pending"
    )
    db_session.add(payment)
    await db_session.flush()
    h = _h(_token(test_user, test_club))
    assert (
        await client.put(
            f"/api/v1/payments/{payment.id}",
            headers=h,
            json={"training_enrollment_id": str(enr.id)},
        )
    ).status_code == 422
    payment.person_id = person.id
    payment.training_enrollment_id = enr.id
    enr.status = "cancelled"
    await db_session.flush()
    r = await client.put(
        f"/api/v1/payments/{payment.id}",
        headers=h,
        json={"training_enrollment_id": str(enr.id), "status": "paid"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "paid"


async def test_list_filter_never_broadens_guardian_scope(client, db_session, test_club):
    person, _, enr = await _setup(db_session, test_club)
    guardian = await _person(db_session, test_club)
    user = await _user(db_session, test_club, role="veli", person=guardian)
    db_session.add(
        Payment(
            club_id=test_club.id,
            person_id=person.id,
            training_enrollment_id=enr.id,
            amount=1000,
            status="paid",
        )
    )
    await db_session.flush()
    h = _h(_token(user, test_club))
    r = await client.get(
        "/api/v1/payments", params={"training_enrollment_id": str(enr.id)}, headers=h
    )
    assert r.status_code == 200
    assert r.json()["items"] == []
