import uuid

import pytest
from app.models.person import Person
from app.models.person_guardian import PersonGuardian
from app.models.user import User
from sqlalchemy import select

from tests.test_antrenor_scope import _h, _person, _token, _user

pytestmark = pytest.mark.asyncio
URL = "/api/v1/persons/athlete-registration"


@pytest.mark.parametrize("role", ["antrenor", "basantrenor", "kulup_yonetici"])
@pytest.mark.parametrize("mode", ["none", "existing", "new"])
async def test_one_step_registration(client, db_session, test_club, role, mode):
    user = await _user(db_session, test_club, role=role, person=await _person(db_session, test_club))
    h = _h(_token(user, test_club))
    body = {"athlete": {"first_name": "Yeni", "last_name": "Sporcu", "role_codes": ["sporcu"]}}
    if mode == "existing":
        parent = await _person(db_session, test_club, first_name="Existing", role_codes=["veli"])
        body["guardian_person_id"] = str(parent.id)
        search = await client.get("/api/v1/persons/guardian-options", params={"search": "Existing"}, headers=h)
        assert search.status_code == 200
        assert search.json()[0]["id"] == str(parent.id)
    elif mode == "new":
        body["new_guardian"] = {"first_name": "Yeni", "last_name": "Veli", "role_codes": ["veli"]}
    result = await client.post(URL, json=body, headers=h)
    assert result.status_code == 201, result.text
    athlete_id = uuid.UUID(result.json()["id"])
    links = (await db_session.execute(select(PersonGuardian).where(PersonGuardian.athlete_person_id == athlete_id))).scalars().all()
    assert len(links) == (0 if mode == "none" else 1)
    if links:
        assert links[0].is_primary
        assert not links[0].can_consent
        assert (await db_session.execute(select(User).where(User.person_id == links[0].guardian_person_id))).scalar_one_or_none() is None
    assert (await client.get(f"/api/v1/athletes/{athlete_id}", headers=h)).status_code == 200


@pytest.mark.parametrize("invalid", ["missing", "duplicate_email", "both", "account", "wrong_kind"])
async def test_invalid_parent_leaves_no_partial_athlete(client, db_session, test_club, invalid):
    coach = await _user(db_session, test_club, person=await _person(db_session, test_club))
    name = uuid.uuid4().hex
    body = {"athlete": {"first_name": name, "last_name": "Rollback", "role_codes": ["sporcu"]}}
    if invalid in {"missing", "both"}:
        body["guardian_person_id"] = str(uuid.uuid4())
    if invalid in {"duplicate_email", "both", "account", "wrong_kind"}:
        body["new_guardian"] = {"first_name": "New", "last_name": "Parent", "role_codes": ["veli"]}
    if invalid == "duplicate_email":
        existing = await _person(db_session, test_club, role_codes=["veli"])
        body["new_guardian"]["email"] = existing.email
    elif invalid == "account":
        body["new_guardian"]["create_account"] = True
    elif invalid == "wrong_kind":
        body["new_guardian"]["role_codes"] = ["antrenor"]
    result = await client.post(URL, json=body, headers=_h(_token(coach, test_club)))
    assert result.status_code in {403, 404, 409, 422}, result.text
    assert (await db_session.execute(select(Person).where(Person.first_name == name))).scalars().all() == []


async def test_registration_keeps_tenant_and_role_boundaries(client, db_session, test_club):
    from app.models.club import Club
    coach = await _user(db_session, test_club, person=await _person(db_session, test_club))
    club = Club(name="Other", slug=uuid.uuid4().hex, settings={})
    db_session.add(club)
    await db_session.flush()
    parent = await _person(db_session, club, role_codes=["veli"])
    h = _h(_token(coach, test_club))
    body = {"athlete": {"first_name": "Cross", "last_name": "Club", "role_codes": ["sporcu"]}, "guardian_person_id": str(parent.id)}
    assert (await client.post(URL, json=body, headers=h)).status_code == 404
    assert (await db_session.execute(select(Person).where(Person.first_name == "Cross"))).scalars().all() == []
    outsider = await _user(db_session, test_club, role="veli", person=await _person(db_session, test_club))
    denied = _h(_token(outsider, test_club))
    assert (await client.get("/api/v1/persons/guardian-options", params={"search": "Test"}, headers=denied)).status_code == 403
    assert (await client.post(URL, json=body, headers=denied)).status_code == 403
