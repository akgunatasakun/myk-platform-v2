"""Kulüp sertifikası durum geçişleri, değişmez kayıt ve nesne bazlı yetki matrisi."""

import csv
import io
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.api.v1.routers.certificates import MANAGERS, READERS, now
from app.models.audit import AuditLog
from app.models.club import Club
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
URL = "/api/v1/certificates"


async def setup(db, club):
    person = await _person(db, club, first_name="Deniz", role_codes=["sporcu"])
    course = await _course(db, club, name="YTE D1")
    enr = await _enroll(db, club, course, person)
    return person, course, enr


async def draft(client, headers, enr):
    r = await client.post(
        URL,
        headers=headers,
        json={
            "enrollment_id": str(enr.id),
            "title": "YTE D1 Kulüp Eğitim Sertifikası",
            "notes": "Yalnız yönetim notu",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def issue(client, headers, item, *, expired=False):
    today = now().date()
    r = await client.post(
        f"{URL}/{item['id']}/issue",
        headers=headers,
        json={
            "issued_on": str(today - timedelta(days=10)),
            "expires_on": str(today - timedelta(days=1)) if expired else None,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_draft_issue_revoke_and_replacement(
    client, db_session, test_club, test_user
):
    person, _, enr = await setup(db_session, test_club)
    h = _h(_token(test_user, test_club))
    item = await draft(client, h, enr)
    assert item["status"] == "draft" and item["number"] is None
    assert (
        await client.patch(
            f"{URL}/{item['id']}", headers=h, json={"title": "D1 Eğitim Sertifikası"}
        )
    ).status_code == 200
    person.first_name = "Güncel İsim"
    await db_session.flush()
    issued = await issue(client, h, item)
    assert issued["status"] == issued["state"] == "issued"
    assert issued["number"].startswith("MYK-SRT-")
    assert issued["person_name"].startswith("Güncel İsim")
    person.first_name = "Sonraki İsim"
    await db_session.flush()
    detail = await client.get(f"{URL}/{item['id']}", headers=h)
    assert detail.json()["person_name"] == issued["person_name"]
    assert (
        await client.patch(
            f"{URL}/{item['id']}", headers=h, json={"title": "Değişmesin"}
        )
    ).status_code == 409
    assert (await client.delete(f"{URL}/{item['id']}", headers=h)).status_code == 409
    assert (
        await client.post(
            f"{URL}/{item['id']}/issue",
            headers=h,
            json={"issued_on": str(now().date())},
        )
    ).status_code == 409
    r = await client.post(
        f"{URL}/{item['id']}/revoke", headers=h, json={"reason": "Düzeltme için iptal"}
    )
    assert r.status_code == 200 and r.json()["status"] == "revoked"
    replacement = await draft(client, h, enr)
    assert replacement["id"] != item["id"]
    actions = (
        (
            await db_session.execute(
                select(AuditLog.action).where(AuditLog.club_id == test_club.id)
            )
        )
        .scalars()
        .all()
    )
    assert {
        "certificate_drafted",
        "certificate_updated",
        "certificate_issued",
        "certificate_revoked",
    }.issubset(set(actions))


@pytest.mark.parametrize(
    "role",
    sorted(
        READERS
        | {
            "uye",
            "misafir",
            "muhasebe",
            "personel",
            "saglik_sorumlusu",
            "guvenlik_operasyon",
        }
    ),
)
async def test_role_matrix(client, db_session, test_club, test_user, role):
    person, course, enr = await setup(db_session, test_club)
    admin = _h(_token(test_user, test_club))
    item = await draft(client, admin, enr)
    await issue(client, admin, item)
    actor = await _person(db_session, test_club)
    if role == "sporcu":
        actor = person
    elif role == "veli":
        db_session.add(
            PersonGuardian(
                club_id=test_club.id,
                guardian_person_id=actor.id,
                athlete_person_id=person.id,
            )
        )
    elif role in {"antrenor", "basantrenor"}:
        await _assign_course_instructor(db_session, test_club, course, actor)
    user = await _user(db_session, test_club, role=role, person=actor)
    h = _h(_token(user, test_club))
    listing = await client.get(URL, headers=h)
    detail = await client.get(f"{URL}/{item['id']}", headers=h)
    export = await client.get(URL + "/export", headers=h)
    if role in READERS:
        assert listing.status_code == detail.status_code == export.status_code == 200
        assert listing.json()["total"] == 1
        assert (detail.json()["notes"] is not None) == (role in MANAGERS)
    else:
        assert listing.status_code == detail.status_code == export.status_code == 403
    options = await client.get(URL + "/enrollment-options", headers=h)
    assert options.status_code == (200 if role in MANAGERS else 403)
    write = await client.patch(f"{URL}/{item['id']}", headers=h, json={"title": "Yeni"})
    assert write.status_code == (409 if role in MANAGERS else 403)
    for action, payload in [
        ("issue", {"issued_on": str(now().date())}),
        ("revoke", {"reason": "Test"}),
    ]:
        if role not in MANAGERS:
            assert (
                await client.post(
                    f"{URL}/{item['id']}/{action}", headers=h, json=payload
                )
            ).status_code == 403


@pytest.mark.parametrize("role", ["veli", "sporcu", "antrenor", "basantrenor"])
async def test_outside_scope_and_draft_privacy(
    client, db_session, test_club, test_user, role
):
    _, _, enr = await setup(db_session, test_club)
    admin = _h(_token(test_user, test_club))
    item = await draft(client, admin, enr)
    actor = await _person(db_session, test_club)
    user = await _user(db_session, test_club, role=role, person=actor)
    h = _h(_token(user, test_club))
    for issued in [False, True]:
        if issued:
            await issue(client, admin, item)
        listing = await client.get(
            URL, params={"enrollment_id": str(enr.id)}, headers=h
        )
        assert listing.status_code == 200 and listing.json()["items"] == []
        assert (await client.get(f"{URL}/{item['id']}", headers=h)).status_code == 404
        assert "YTE D1" not in (await client.get(URL + "/export", headers=h)).text


async def test_active_guardian_sees_only_issued_and_revocation_history(
    client, db_session, test_club, test_user
):
    person, _, enr = await setup(db_session, test_club)
    guardian = await _person(db_session, test_club)
    user = await _user(db_session, test_club, role="veli", person=guardian)
    link = PersonGuardian(
        club_id=test_club.id,
        guardian_person_id=guardian.id,
        athlete_person_id=person.id,
    )
    db_session.add(link)
    await db_session.flush()
    admin, h = _h(_token(test_user, test_club)), _h(_token(user, test_club))
    item = await draft(client, admin, enr)
    assert (await client.get(URL, headers=h)).json()["total"] == 0
    await issue(client, admin, item)
    assert (await client.get(URL, headers=h)).json()["total"] == 1
    await client.post(
        f"{URL}/{item['id']}/revoke", headers=admin, json={"reason": "Düzeltme"}
    )
    assert (await client.get(f"{URL}/{item['id']}", headers=h)).json()[
        "status"
    ] == "revoked"
    link.is_active = False
    await db_session.flush()
    assert (await client.get(URL, headers=h)).json()["total"] == 0
    assert (await client.get(f"{URL}/{item['id']}", headers=h)).status_code == 404


async def test_duplicate_draft_rejected(client, db_session, test_club, test_user):
    _, _, enr = await setup(db_session, test_club)
    h = _h(_token(test_user, test_club))
    item = await draft(client, h, enr)
    duplicate = await client.post(
        URL, headers=h, json={"enrollment_id": str(enr.id), "title": "Yinelenen"}
    )
    assert duplicate.status_code == 409
    assert (await client.get(URL, headers=h)).json()["total"] == 1
    assert (await client.delete(f"{URL}/{item['id']}", headers=h)).status_code == 204
    assert (await client.get(URL, headers=h)).json()["total"] == 0
    await draft(client, h, enr)


@pytest.mark.parametrize("invalid", ["future", "expiry", "cancelled", "deleted_course"])
async def test_issue_validation(client, db_session, test_club, test_user, invalid):
    _, course, enr = await setup(db_session, test_club)
    h = _h(_token(test_user, test_club))
    item = await draft(client, h, enr)
    today = now().date()
    body = {"issued_on": str(today)}
    expected = 422
    if invalid == "future":
        body["issued_on"] = str(today + timedelta(days=1))
    elif invalid == "expiry":
        body["expires_on"] = str(today - timedelta(days=1))
    elif invalid == "cancelled":
        enr.status = "cancelled"
        expected = 409
    else:
        course.is_deleted = True
        expected = 404
    await db_session.flush()
    assert (
        await client.post(f"{URL}/{item['id']}/issue", headers=h, json=body)
    ).status_code == expected
    assert (await client.get(f"{URL}/{item['id']}", headers=h)).json()[
        "status"
    ] == "draft"


async def test_cross_tenant_ids_and_choices(client, db_session, test_club, test_user):
    other = Club(id=uuid.uuid4(), slug=uuid.uuid4().hex, name="Diğer Kulüp")
    db_session.add(other)
    await db_session.flush()
    _, _, enr = await setup(db_session, other)
    h = _h(_token(test_user, test_club))
    assert (
        await client.post(
            URL, headers=h, json={"enrollment_id": str(enr.id), "title": "Yabancı"}
        )
    ).status_code == 404
    choices = await client.get(
        URL + "/enrollment-options", headers=h, params={"enrollment_id": str(enr.id)}
    )
    assert choices.status_code == 200 and choices.json() == []
    other_admin = await _user(db_session, other, role="kulup_yonetici")
    item = await draft(client, _h(_token(other_admin, other)), enr)
    assert (await client.get(f"{URL}/{item['id']}", headers=h)).status_code == 404
    assert (
        await client.patch(f"{URL}/{item['id']}", headers=h, json={"title": "X"})
    ).status_code == 404


async def test_filters_csv_escape_and_issued_archive(
    client, db_session, test_club, test_user
):
    _, course, enr = await setup(db_session, test_club)
    h = _h(_token(test_user, test_club))
    item = await draft(client, h, enr)
    assert (
        await client.patch(
            f"{URL}/{item['id']}", headers=h, json={"title": '=HYPERLINK("test")'}
        )
    ).status_code == 200
    issued = await issue(client, h, item, expired=True)
    assert issued["state"] == "expired"
    assert (
        await client.get(
            URL, headers=h, params={"state": "expired", "course_id": str(course.id)}
        )
    ).json()["total"] == 1
    assert (await client.get(URL, headers=h, params={"state": "issued"})).json()[
        "total"
    ] == 0
    assert (
        await client.get(URL, headers=h, params={"search": issued["number"]})
    ).json()["total"] == 1
    response = await client.get(URL + "/export", headers=h, params={"state": "expired"})
    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.text.lstrip("\ufeff")), delimiter=";"))
    assert len(rows) == 2
    assert rows[1][3].startswith("'=HYPERLINK")
    course.is_deleted = True
    enr.status = "cancelled"
    await db_session.flush()
    assert (await client.get(f"{URL}/{item['id']}", headers=h)).json()[
        "number"
    ] == issued["number"]


async def test_choices_search_excludes_open_certificate(
    client, db_session, test_club, test_user
):
    _, course, enr = await setup(db_session, test_club)
    h = _h(_token(test_user, test_club))
    choices = await client.get(
        URL + "/enrollment-options",
        params={"search": "Deniz", "course_id": str(course.id)},
        headers=h,
    )
    assert choices.status_code == 200
    assert [x["id"] for x in choices.json()] == [str(enr.id)]
    await draft(client, h, enr)
    assert (
        await client.get(
            URL + "/enrollment-options",
            params={"enrollment_id": str(enr.id)},
            headers=h,
        )
    ).json() == []


async def test_pagination_and_state_validation(
    client, db_session, test_club, test_user
):
    _, _, enr = await setup(db_session, test_club)
    h = _h(_token(test_user, test_club))
    item = await draft(client, h, enr)
    assert (await client.get(URL, headers=h, params={"skip": 1, "limit": 1})).json()[
        "items"
    ] == []
    assert (
        await client.get(URL, headers=h, params={"state": "invalid"})
    ).status_code == 422
    assert (
        await client.post(
            f"{URL}/{item['id']}/revoke", headers=h, json={"reason": "Geçersiz geçiş"}
        )
    ).status_code == 409
    assert (
        await client.patch(f"{URL}/{item['id']}", headers=h, json={"title": "   "})
    ).status_code == 422
    await issue(client, h, item)
    assert (
        await client.post(
            f"{URL}/{item['id']}/revoke", headers=h, json={"reason": "   "}
        )
    ).status_code == 422


async def test_course_filter_never_exposes_other_course(
    client, db_session, test_club, test_user
):
    _, course, enr = await setup(db_session, test_club)
    _, other_course, other_enr = await setup(db_session, test_club)
    h = _h(_token(test_user, test_club))
    await draft(client, h, enr)
    await draft(client, h, other_enr)
    r = await client.get(
        URL, headers=h, params={"course_id": str(course.id), "limit": 1}
    )
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["course_id"] == str(course.id)
    assert other_course.id != course.id
