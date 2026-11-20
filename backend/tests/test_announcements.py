"""Duyuru hedef kitlesi, yayın aralığı, CRUD ve kulüp izolasyonu."""

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from app.core.security import create_access_token
from app.models.announcement import Announcement, AnnouncementAudience
from app.models.audit import AuditLog
from app.models.club import Club
from sqlalchemy import select

pytestmark = pytest.mark.asyncio


def headers(user, club):
    return {
        "Authorization": "Bearer "
        + create_access_token(str(user.id), str(club.id), user.role)
    }


async def add(db, club, title="Duyuru", status="yayinda", roles=None, **kwargs):
    a = Announcement(
        club_id=club.id, title=title, body="Kulüp duyurusu", status=status, **kwargs
    )
    a.audiences = [AnnouncementAudience(role_code=r) for r in roles or []]
    db.add(a)
    await db.flush()
    return a


async def test_lifecycle_and_audit(client, db_session, test_club, test_user):
    h = headers(test_user, test_club)
    data = {
        "title": "  Yeni dönem  ",
        "body": " Ders saatleri ",
        "target_roles": ["veli", "sporcu", "veli"],
    }
    r = await client.post("/api/v1/announcements", headers=h, json=data)
    assert r.status_code == 201, r.text
    a = r.json()
    aid = a["id"]
    assert a["title"] == "Yeni dönem" and a["target_roles"] == ["sporcu", "veli"]
    assert (await client.get("/api/v1/announcements", headers=h)).json()["total"] == 0
    assert (await client.get("/api/v1/announcements?manage=true", headers=h)).json()[
        "total"
    ] == 1
    data = {**data, "status": "yayinda", "target_roles": []}
    r = await client.put(f"/api/v1/announcements/{aid}", headers=h, json=data)
    assert r.status_code == 200, r.text
    assert r.json()["target_roles"] == []
    assert (await client.get("/api/v1/announcements", headers=h)).json()["total"] == 1
    data["status"] = "arsiv"
    assert (
        await client.put(f"/api/v1/announcements/{aid}", headers=h, json=data)
    ).status_code == 200
    assert (await client.get("/api/v1/announcements", headers=h)).json()["total"] == 0
    assert (
        await client.delete(f"/api/v1/announcements/{aid}", headers=h)
    ).status_code == 204
    assert (await client.get("/api/v1/announcements?manage=true", headers=h)).json()[
        "total"
    ] == 0
    assert (
        await client.put(f"/api/v1/announcements/{aid}", headers=h, json=data)
    ).status_code == 404
    actions = (
        (
            await db_session.execute(
                select(AuditLog.action).where(AuditLog.resource_id == aid)
            )
        )
        .scalars()
        .all()
    )
    assert actions == [
        "announcement_created",
        "announcement_updated",
        "announcement_updated",
        "announcement_deleted",
    ]


async def test_audience_and_date_scope(client, db_session, test_club, test_user):
    today = datetime.now(ZoneInfo("Europe/Istanbul")).date()
    await add(db_session, test_club, "Herkese")
    await add(
        db_session,
        test_club,
        "Velilere",
        roles=["veli"],
        starts_on=today,
        ends_on=today,
    )
    await add(db_session, test_club, "Sporculara", roles=["sporcu"])
    await add(db_session, test_club, "Taslak", status="taslak")
    await add(db_session, test_club, "Arşiv", status="arsiv")
    await add(db_session, test_club, "Gelecek", starts_on=today + timedelta(days=1))
    await add(db_session, test_club, "Eski", ends_on=today - timedelta(days=1))
    test_user.role = "veli"
    h = headers(test_user, test_club)
    r = (await client.get("/api/v1/announcements", headers=h)).json()
    assert {a["title"] for a in r["items"]} == {"Herkese", "Velilere"}
    assert r["total"] == 2
    assert (
        await client.get("/api/v1/announcements?manage=true", headers=h)
    ).status_code == 403
    assert (await client.get("/api/v1/announcements?status=taslak", headers=h)).json()[
        "total"
    ] == 0


@pytest.mark.parametrize(
    "role", ["veli", "sporcu", "uye", "misafir", "antrenor", "personel", "yk_uyesi"]
)
async def test_nonmanager_write_denied(client, db_session, test_club, test_user, role):
    a = await add(db_session, test_club)
    test_user.role = role
    h = headers(test_user, test_club)
    data = {"title": "x", "body": "x"}
    assert (
        await client.post("/api/v1/announcements", headers=h, json=data)
    ).status_code == 403
    assert (
        await client.put(f"/api/v1/announcements/{a.id}", headers=h, json=data)
    ).status_code == 403
    assert (
        await client.delete(f"/api/v1/announcements/{a.id}", headers=h)
    ).status_code == 403


async def test_other_club_hidden(client, db_session, test_club, test_user):
    c = Club(slug=uuid.uuid4().hex, name="Başka", plan="starter", settings={})
    db_session.add(c)
    await db_session.flush()
    a = await add(db_session, c)
    h = headers(test_user, test_club)
    for query in ("", "?manage=true"):
        assert (await client.get("/api/v1/announcements" + query, headers=h)).json()[
            "total"
        ] == 0
    assert (
        await client.put(
            f"/api/v1/announcements/{a.id}", headers=h, json={"title": "x", "body": "x"}
        )
    ).status_code == 404
    assert (
        await client.delete(f"/api/v1/announcements/{a.id}", headers=h)
    ).status_code == 404


@pytest.mark.parametrize(
    "extra",
    [
        {"title": "  "},
        {"body": "  "},
        {"status": "bad"},
        {"target_roles": ["bad"]},
        {"starts_on": "2026-12-02", "ends_on": "2026-12-01"},
        {"club_id": str(uuid.uuid4())},
    ],
)
async def test_validation(client, test_club, test_user, extra):
    assert (
        await client.post(
            "/api/v1/announcements",
            headers=headers(test_user, test_club),
            json={"title": "Başlık", "body": "Metin", **extra},
        )
    ).status_code == 422


async def test_filters_paging_and_important_first(
    client, db_session, test_club, test_user
):
    await add(db_session, test_club, "Normal")
    a = await add(db_session, test_club, "Önemli", important=True)
    await add(db_session, test_club, "Taslak", status="taslak")
    h = headers(test_user, test_club)
    r = (await client.get("/api/v1/announcements?limit=1", headers=h)).json()
    assert r["total"] == 2 and r["items"][0]["id"] == str(a.id)
    assert (
        len(
            (
                await client.get("/api/v1/announcements?skip=1&limit=1", headers=h)
            ).json()["items"]
        )
        == 1
    )
    assert (
        await client.get("/api/v1/announcements?manage=true&status=taslak", headers=h)
    ).json()["total"] == 1
    assert (await client.get("/api/v1/announcements?search=%25", headers=h)).json()[
        "total"
    ] == 0
