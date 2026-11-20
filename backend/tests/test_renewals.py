"""Yenileme dönemi geçmişi, uyarılar ve yetki sınırları."""

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from app.core.security import create_access_token
from app.models.club import Club
from app.models.documents import Document
from app.models.renewal import DocumentRenewal
from app.models.user import User

pytestmark = pytest.mark.asyncio


def headers(user, club):
    return {
        "Authorization": "Bearer "
        + create_access_token(str(user.id), str(club.id), user.role)
    }


async def document(db, club):
    d = Document(
        club_id=club.id,
        code="MYK-POL-TEST",
        title="Test Poliçesi",
        document_type="diger",
    )
    db.add(d)
    await db.flush()
    return d


async def test_period_history_and_missing_dates(
    client, db_session, test_club, test_user
):
    doc = await document(db_session, test_club)
    h = headers(test_user, test_club)
    data = {
        "document_id": str(doc.id),
        "kind": "police",
        "responsible_user_id": str(test_user.id),
    }
    r = await client.post("/api/v1/renewals", headers=h, json=data)
    assert r.status_code == 201, r.text
    old = r.json()
    assert old["state"] == "eksik" and old["responsible_name"] == test_user.full_name
    assert (await client.get("/api/v1/renewals?view=uyari", headers=h)).json()[
        "total"
    ] == 1
    assert (
        await client.post("/api/v1/renewals", headers=h, json=data)
    ).status_code == 409


async def test_renewal_retains_old_period(client, db_session, test_club, test_user):
    doc = await document(db_session, test_club)
    h = headers(test_user, test_club)
    data = {
        "document_id": str(doc.id),
        "kind": "police",
        "starts_on": "2025-11-11",
        "expires_on": "2026-11-11",
    }
    r = await client.post("/api/v1/renewals", headers=h, json=data)
    aid = r.json()["id"]
    assert r.json()["state"] == "gecikti"
    next_data = {**data, "starts_on": "2026-11-11", "expires_on": "2027-11-11"}
    r = await client.post(f"/api/v1/renewals/{aid}/renew", headers=h, json=next_data)
    assert r.status_code == 201, r.text
    assert r.json()["previous_id"] == aid
    active = (await client.get("/api/v1/renewals", headers=h)).json()
    history = (await client.get("/api/v1/renewals?view=gecmis", headers=h)).json()
    assert active["total"] == history["total"] == 1
    assert history["items"][0]["expires_on"] == "2026-11-11"
    assert history["items"][0]["state"] == "kapali"
    assert (
        await client.post(f"/api/v1/renewals/{aid}/renew", headers=h, json=next_data)
    ).status_code == 409
    assert (
        await client.put(f"/api/v1/renewals/{aid}", headers=h, json=data)
    ).status_code == 409


@pytest.mark.parametrize(
    "dates",
    [
        {},
        {"starts_on": "2026-01-01", "expires_on": "2027-01-01"},
        {"starts_on": "2026-11-11", "expires_on": "2026-11-11"},
    ],
)
async def test_invalid_new_period_leaves_old_open(
    client, db_session, test_club, test_user, dates
):
    d = await document(db_session, test_club)
    h = headers(test_user, test_club)
    data = {"document_id": str(d.id), "kind": "sozlesme", "expires_on": "2026-11-11"}
    old = (await client.post("/api/v1/renewals", headers=h, json=data)).json()
    r = await client.post(
        f"/api/v1/renewals/{old['id']}/renew",
        headers=h,
        json={"document_id": str(d.id), "kind": "sozlesme", **dates},
    )
    assert r.status_code == 422
    assert (await client.get("/api/v1/renewals", headers=h)).json()["total"] == 1
    assert (await client.get("/api/v1/renewals?view=gecmis", headers=h)).json()[
        "total"
    ] == 0


async def test_due_boundaries_and_filters(client, db_session, test_club, test_user):
    today = datetime.now(ZoneInfo("Europe/Istanbul")).date()
    for days in (None, -1, 0, 30, 31):
        d = await document(db_session, test_club)
        db_session.add(
            DocumentRenewal(
                club_id=test_club.id,
                document_id=d.id,
                kind="police",
                warning_days=30,
                expires_on=today + timedelta(days=days) if days is not None else None,
            )
        )
    await db_session.flush()
    h = headers(test_user, test_club)
    r = (await client.get("/api/v1/renewals?view=uyari&limit=2", headers=h)).json()
    assert r["total"] == 4 and len(r["items"]) == 2
    assert (await client.get("/api/v1/renewals?view=gecikti", headers=h)).json()[
        "total"
    ] == 1
    assert (await client.get("/api/v1/renewals?view=eksik", headers=h)).json()[
        "total"
    ] == 1
    assert (await client.get("/api/v1/renewals?kind=sozlesme", headers=h)).json()[
        "total"
    ] == 0
    assert (await client.get("/api/v1/renewals?search=%25", headers=h)).json()[
        "total"
    ] == 0


@pytest.mark.parametrize(
    "role", ["veli", "sporcu", "uye", "antrenor", "personel", "misafir"]
)
async def test_unrelated_roles_denied(client, test_club, test_user, role):
    test_user.role = role
    assert (
        await client.get("/api/v1/renewals", headers=headers(test_user, test_club))
    ).status_code == 403


@pytest.mark.parametrize("role", ["baskan", "yk_uyesi", "muhasebe"])
async def test_readonly_roles(client, db_session, test_club, test_user, role):
    d = await document(db_session, test_club)
    test_user.role = role
    h = headers(test_user, test_club)
    assert (await client.get("/api/v1/renewals", headers=h)).status_code == 200
    assert (
        await client.post(
            "/api/v1/renewals",
            headers=h,
            json={"document_id": str(d.id), "kind": "police"},
        )
    ).status_code == 403


async def test_cross_club_and_responsible_validation(
    client, db_session, test_club, test_user
):
    other = Club(slug=uuid.uuid4().hex, name="Başka", plan="starter", settings={})
    db_session.add(other)
    await db_session.flush()
    d = await document(db_session, other)
    old = DocumentRenewal(club_id=other.id, document_id=d.id, kind="police")
    db_session.add(old)
    await db_session.flush()
    h = headers(test_user, test_club)
    data = {"document_id": str(d.id), "kind": "police"}
    assert (await client.get("/api/v1/renewals", headers=h)).json()["total"] == 0
    assert (await client.get("/api/v1/renewals/documents", headers=h)).json() == []
    assert (
        await client.post("/api/v1/renewals", headers=h, json=data)
    ).status_code == 404
    assert (
        await client.put(f"/api/v1/renewals/{old.id}", headers=h, json=data)
    ).status_code == 404
    local = await document(db_session, test_club)
    bad_user = User(
        club_id=test_club.id,
        email=uuid.uuid4().hex + "@test.com",
        full_name="Antrenör",
        role="antrenor",
        password_hash="unused",
    )
    db_session.add(bad_user)
    await db_session.flush()
    data = {
        "document_id": str(local.id),
        "kind": "police",
        "responsible_user_id": str(bad_user.id),
    }
    assert (
        await client.post("/api/v1/renewals", headers=h, json=data)
    ).status_code == 422


@pytest.mark.parametrize(
    "extra",
    [
        {"warning_days": 0},
        {"warning_days": 366},
        {"kind": "bad"},
        {"starts_on": "2026-12-02", "expires_on": "2026-12-01"},
    ],
)
async def test_input_validation(client, db_session, test_club, test_user, extra):
    d = await document(db_session, test_club)
    assert (
        await client.post(
            "/api/v1/renewals",
            headers=headers(test_user, test_club),
            json={"document_id": str(d.id), "kind": "police", **extra},
        )
    ).status_code == 422


async def test_close_reopen_and_protect_renewed_history(
    client, db_session, test_club, test_user
):
    d = await document(db_session, test_club)
    h = headers(test_user, test_club)
    data = {"document_id": str(d.id), "kind": "police", "expires_on": "2026-11-11"}
    old = (await client.post("/api/v1/renewals", headers=h, json=data)).json()
    path = f"/api/v1/renewals/{old['id']}/closure"
    assert (
        await client.patch(path, headers=h, json={"is_closed": True})
    ).status_code == 200
    assert (await client.get("/api/v1/renewals?view=uyari", headers=h)).json()[
        "total"
    ] == 0
    assert (
        await client.patch(path, headers=h, json={"is_closed": False})
    ).status_code == 200
    new = {**data, "starts_on": "2026-11-11", "expires_on": "2027-11-11"}
    assert (
        await client.post(f"/api/v1/renewals/{old['id']}/renew", headers=h, json=new)
    ).status_code == 201
    assert (
        await client.patch(path, headers=h, json={"is_closed": False})
    ).status_code == 409
