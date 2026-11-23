import uuid

import pytest
from app.models.club import Club
from app.models.person import Person
from app.models.user import User
from sqlalchemy import select

from tests.test_antrenor_scope import _h, _person, _token, _user

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("role", ["antrenor", "basantrenor"])
async def test_coach_creates_and_reads_only_own_new_athlete(client, db_session, test_club, role):
    coach = await _user(db_session, test_club, role=role, person=await _person(db_session, test_club))
    other_coach = await _user(db_session, test_club, role=role, person=await _person(db_session, test_club))
    outsider = await _person(db_session, test_club, role_codes=["sporcu"])
    h = _h(_token(coach, test_club))
    r = await client.post("/api/v1/persons", headers=h, json={"first_name": "Yeni", "last_name": "Sporcu", "role_codes": ["sporcu"], "email": f"{uuid.uuid4().hex}@example.com"})
    assert r.status_code == 201, r.text
    person_id = r.json()["id"]
    assert r.json()["role_codes"] == ["sporcu"]
    assert r.json()["temp_password"] is None
    created = await db_session.get(Person, uuid.UUID(person_id))
    assert created.club_id == test_club.id
    assert created.created_by_user_id == coach.id
    assert (await db_session.execute(select(User).where(User.person_id == created.id))).scalar_one_or_none() is None
    for path in ("/api/v1/athletes", "/api/v1/athletes/alerts"):
        result = (await client.get(path, headers=h)).json()
        rows = result["items"] if isinstance(result, dict) else result
        assert {row["person_id"] for row in rows} == {person_id}
    assert (await client.get(f"/api/v1/athletes/{person_id}", headers=h)).status_code == 200
    assert (await client.get(f"/api/v1/athletes/{person_id}", headers=_h(_token(other_coach, test_club)))).status_code == 403
    assert (await client.get(f"/api/v1/athletes/{outsider.id}", headers=h)).status_code == 403
    assert (await client.patch(f"/api/v1/persons/{person_id}", headers=h, json={"first_name": "Changed"})).status_code == 403
    assert (await client.delete(f"/api/v1/persons/{person_id}", headers=h)).status_code == 403
    assert (await client.patch(f"/api/v1/athletes/{person_id}", headers=h, json={"level": "elit"})).status_code == 403


@pytest.mark.parametrize("payload", [
    {"role_codes": ["antrenor"]}, {"role_codes": ["sporcu", "uye"]},
    {"role_codes": []}, {"role_codes": ["sporcu"], "create_account": True},
])
async def test_coach_cannot_create_other_kinds_or_accounts(client, db_session, test_club, payload):
    coach = await _user(db_session, test_club, person=await _person(db_session, test_club))
    r = await client.post("/api/v1/persons", headers=_h(_token(coach, test_club)), json={"first_name": "Forbidden", "last_name": "Person", **payload})
    assert r.status_code == 403
    assert (await db_session.execute(select(Person).where(Person.first_name == "Forbidden"))).scalars().all() == []


async def test_creator_cannot_be_forged_and_tenant_scope_remains(client, db_session, test_club):
    coach = await _user(db_session, test_club, person=await _person(db_session, test_club))
    h = _h(_token(coach, test_club))
    r = await client.post("/api/v1/persons", headers=h, json={"first_name": "Test", "last_name": "Test", "role_codes": ["sporcu"], "created_by_user_id": str(coach.id)})
    assert r.status_code == 422
    other_club = Club(name="Other", slug=uuid.uuid4().hex, settings={})
    db_session.add(other_club)
    await db_session.flush()
    cross = await _person(db_session, other_club, role_codes=["sporcu"])
    cross.created_by_user_id = coach.id
    await db_session.flush()
    assert (await client.get(f"/api/v1/athletes/{cross.id}", headers=h)).status_code == 404
    assert (await client.get("/api/v1/athletes", headers=h)).json()["items"] == []


@pytest.mark.parametrize("role", ["veli", "sporcu", "uye", "misafir", "muhasebe"])
async def test_other_readers_cannot_create_athletes(client, db_session, test_club, role):
    user = await _user(db_session, test_club, role=role, person=await _person(db_session, test_club))
    assert (await client.post("/api/v1/persons", headers=_h(_token(user, test_club)), json={"first_name": "No", "last_name": "Write", "role_codes": ["sporcu"]})).status_code == 403


async def test_unlinked_coach_cannot_create(client, db_session, test_club):
    coach = await _user(db_session, test_club)
    assert (await client.post("/api/v1/persons", headers=_h(_token(coach, test_club)), json={"first_name": "No", "last_name": "Link", "role_codes": ["sporcu"]})).status_code == 403


@pytest.mark.parametrize("role", ["antrenor", "basantrenor"])
async def test_coach_assigns_existing_guardian_and_creates_new_atomically(client, db_session, test_club, role):
    from app.models.person_guardian import PersonGuardian
    coach = await _user(db_session, test_club, role=role, person=await _person(db_session, test_club))
    athlete = await _person(db_session, test_club, role_codes=["sporcu"])
    athlete.created_by_user_id = coach.id
    guardian = await _person(db_session, test_club, first_name="Veli", last_name="Aranan", role_codes=["veli"])
    guardian.phone = "05551112233"
    h = _h(_token(coach, test_club))
    await db_session.flush()
    base = f"/api/v1/persons/{athlete.id}"
    options = await client.get(base + "/guardian-options", headers=h, params={"search": "Aranan"})
    assert options.status_code == 200, options.text
    assert options.json()[0]["id"] == str(guardian.id)
    assert options.json()[0]["phone"] == "…2233"
    assert "email" not in options.json()[0]
    assert (await client.get(base + "/guardian-options", headers=h, params={"search": "%%%"})).json() == []
    r = await client.post(base + "/guardians", headers=h, json={"guardian_person_id": str(guardian.id), "relationship_type": "baba"})
    assert r.status_code == 201, r.text
    assert (await client.get(base + "/guardians", headers=h)).json()[0]["guardian_person_id"] == str(guardian.id)
    new = await client.post(base + "/guardians/new", headers=h, json={"person": {"first_name": "Yeni", "last_name": "Anne", "role_codes": ["veli"], "email": f"{uuid.uuid4().hex}@example.com"}, "relationship_type": "anne"})
    assert new.status_code == 201, new.text
    new_id = uuid.UUID(new.json()["id"])
    assert new.json()["temp_password"] is None
    assert (await db_session.execute(select(User).where(User.person_id == new_id))).scalar_one_or_none() is None
    link = (await db_session.execute(select(PersonGuardian).where(PersonGuardian.guardian_person_id == new_id))).scalar_one()
    assert link.athlete_person_id == athlete.id
    link_id = link.id
    assert link.is_active
    assert not link.can_consent
    assert (await client.delete(base + f"/guardians/{link_id}", headers=h)).status_code == 403
    assert (await client.patch(base + f"/guardians/{link_id}", headers=h, json={"is_primary": True})).status_code == 403
    assert (await client.post(base + "/guardians", headers=h, json={"guardian_person_id": str(guardian.id)})).status_code == 409


async def test_guardian_assignment_scope_and_no_orphan_on_rejection(client, db_session, test_club):
    coach = await _user(db_session, test_club, person=await _person(db_session, test_club))
    own = await _person(db_session, test_club, role_codes=["sporcu"])
    own.created_by_user_id = coach.id
    hidden = await _person(db_session, test_club, role_codes=["sporcu"])
    guardian = await _person(db_session, test_club, role_codes=["veli"])
    inactive = await _person(db_session, test_club, first_name="Inactive", role_codes=["veli"])
    inactive.is_active = False
    await db_session.flush()
    h = _h(_token(coach, test_club))
    base = f"/api/v1/persons/{hidden.id}"
    assert (await client.get(base + "/guardian-options", headers=h, params={"search": "Test"})).status_code == 403
    assert (await client.post(base + "/guardians", headers=h, json={"guardian_person_id": str(guardian.id)})).status_code == 403
    assert (await client.post(base + "/guardians/new", headers=h, json={"person": {"first_name": "Orphan", "last_name": "Forbidden", "role_codes": ["veli"]}})).status_code == 403
    assert (await db_session.execute(select(Person).where(Person.first_name == "Orphan"))).scalars().all() == []
    base = f"/api/v1/persons/{own.id}"
    assert (await client.post(base + "/guardians", headers=h, json={"guardian_person_id": str(inactive.id)})).status_code == 403
    assert (await client.post(base + "/guardians", headers=h, json={"guardian_person_id": str(coach.person_id)})).status_code == 403
    for payload in ({"role_codes": ["antrenor"]}, {"role_codes": ["veli"], "create_account": True}):
        r = await client.post(base + "/guardians/new", headers=h, json={"person": {"first_name": "Denied", "last_name": "Guardian", **payload}})
        assert r.status_code == 403
    assert (await db_session.execute(select(Person).where(Person.first_name == "Denied"))).scalars().all() == []
    other_club = Club(name="Other", slug=uuid.uuid4().hex, settings={})
    db_session.add(other_club)
    await db_session.flush()
    foreign = await _person(db_session, other_club, role_codes=["veli"])
    assert (await client.post(base + "/guardians", headers=h, json={"guardian_person_id": str(foreign.id)})).status_code == 404
