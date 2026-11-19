"""Task scope, permissions, validation and lifecycle regressions."""

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from app.core.security import create_access_token
from app.models.audit import AuditLog
from app.models.club import Club
from app.models.person import Person, PersonRole
from app.models.task import Task
from sqlalchemy import select

pytestmark = pytest.mark.asyncio


def headers(user, club):
    return {
        "Authorization": "Bearer "
        + create_access_token(str(user.id), str(club.id), user.role)
    }


async def person(db, club, role="antrenor", active=True):
    p = Person(
        club_id=club.id, first_name="Deniz", last_name="Yelken", is_active=active
    )
    db.add(p)
    await db.flush()
    db.add(PersonRole(person_id=p.id, role_code=role))
    await db.flush()
    return p


async def test_task_lifecycle(client, db_session, test_club, test_user):
    h = headers(test_user, test_club)
    p = await person(db_session, test_club)
    r = await client.post(
        "/api/v1/tasks",
        headers=h,
        json={
            "title": "  Tekne kontrolü  ",
            "assigned_person_id": str(p.id),
            "priority": "acil",
            "due_date": "2026-12-01",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["title"] == "Tekne kontrolü"
    assert r.json()["assigned_person_name"] == "Deniz Yelken"
    task_id = r.json()["id"]
    r = await client.patch(
        f"/api/v1/tasks/{task_id}",
        headers=h,
        json={"status": "tamamlandi", "due_date": None, "assigned_person_id": None},
    )
    assert r.status_code == 200, r.text
    assert r.json()["assigned_person_name"] is None and r.json()["due_date"] is None
    assert (
        await client.delete(f"/api/v1/tasks/{task_id}", headers=h)
    ).status_code == 204
    assert (await client.get("/api/v1/tasks", headers=h)).json()["total"] == 0
    assert (
        await client.patch(f"/api/v1/tasks/{task_id}", headers=h, json={"title": "x"})
    ).status_code == 404
    actions = (
        (
            await db_session.execute(
                select(AuditLog.action).where(AuditLog.resource_id == task_id)
            )
        )
        .scalars()
        .all()
    )
    assert actions == ["task_created", "task_updated", "task_deleted"]


async def test_worker_only_own_status(client, db_session, test_club, test_user):
    p = await person(db_session, test_club)
    test_user.role = "antrenor"
    test_user.person_id = p.id
    own = Task(club_id=test_club.id, title="Kendi görevi", assigned_person_id=p.id)
    other = Task(club_id=test_club.id, title="Başkasının görevi")
    db_session.add_all([own, other])
    await db_session.flush()
    h = headers(test_user, test_club)
    data = (await client.get("/api/v1/tasks", headers=h)).json()
    assert data["total"] == 1 and data["items"][0]["id"] == str(own.id)
    assert (
        await client.patch(
            f"/api/v1/tasks/{own.id}", headers=h, json={"status": "devam_ediyor"}
        )
    ).status_code == 200
    assert (
        await client.patch(
            f"/api/v1/tasks/{own.id}", headers=h, json={"title": "Yetkisiz"}
        )
    ).status_code == 403
    assert (
        await client.patch(
            f"/api/v1/tasks/{other.id}", headers=h, json={"status": "tamamlandi"}
        )
    ).status_code == 404
    assert (
        await client.delete(f"/api/v1/tasks/{own.id}", headers=h)
    ).status_code == 403
    assert (
        await client.post("/api/v1/tasks", headers=h, json={"title": "Yetkisiz"})
    ).status_code == 403
    assert (await client.get("/api/v1/tasks/assignees", headers=h)).status_code == 403


async def test_worker_without_person(client, db_session, test_club, test_user):
    test_user.role = "personel"
    db_session.add(Task(club_id=test_club.id, title="Atanmamış"))
    await db_session.flush()
    assert (
        await client.get("/api/v1/tasks", headers=headers(test_user, test_club))
    ).json()["total"] == 0


async def test_other_club_hidden(client, db_session, test_club, test_user):
    other = Club(slug=uuid.uuid4().hex, name="Başka Kulüp", plan="starter", settings={})
    db_session.add(other)
    await db_session.flush()
    task = Task(club_id=other.id, title="Gizli")
    db_session.add(task)
    await db_session.flush()
    p = await person(db_session, other)
    h = headers(test_user, test_club)
    assert (await client.get("/api/v1/tasks", headers=h)).json()["total"] == 0
    assert (
        await client.patch(f"/api/v1/tasks/{task.id}", headers=h, json={"title": "x"})
    ).status_code == 404
    assert (
        await client.delete(f"/api/v1/tasks/{task.id}", headers=h)
    ).status_code == 404
    assert (
        await client.post(
            "/api/v1/tasks",
            headers=h,
            json={"title": "x", "assigned_person_id": str(p.id)},
        )
    ).status_code == 422
    assert (await client.get("/api/v1/tasks/assignees", headers=h)).json() == []


@pytest.mark.parametrize("role,active", [("sporcu", True), ("antrenor", False)])
async def test_invalid_assignee(client, db_session, test_club, test_user, role, active):
    p = await person(db_session, test_club, role, active)
    h = headers(test_user, test_club)
    assert (
        await client.post(
            "/api/v1/tasks",
            headers=h,
            json={"title": "x", "assigned_person_id": str(p.id)},
        )
    ).status_code == 422
    assert (await client.get("/api/v1/tasks/assignees", headers=h)).json() == []


async def test_filters_and_pagination(client, db_session, test_club, test_user):
    today = datetime.now(ZoneInfo("Europe/Istanbul")).date()
    for title, status, due, priority in [
        ("Eski", "acik", today - timedelta(days=1), "acil"),
        ("Bugün", "devam_ediyor", today, "normal"),
        ("Bitti", "tamamlandi", today - timedelta(days=2), "normal"),
        ("Tarihsiz", "acik", None, "dusuk"),
    ]:
        db_session.add(
            Task(
                club_id=test_club.id,
                title=title,
                status=status,
                due_date=due,
                priority=priority,
            )
        )
    await db_session.flush()
    h = headers(test_user, test_club)
    r = (
        await client.get("/api/v1/tasks?open_only=true&limit=1&skip=1", headers=h)
    ).json()
    assert r["total"] == 3 and r["items"][0]["title"] == "Bugün"
    r = (await client.get("/api/v1/tasks?overdue_only=true", headers=h)).json()
    assert r["total"] == 1 and r["items"][0]["title"] == "Eski"
    assert (await client.get("/api/v1/tasks?priority=dusuk", headers=h)).json()[
        "total"
    ] == 1
    assert (await client.get("/api/v1/tasks?status=tamamlandi", headers=h)).json()[
        "total"
    ] == 1
    assert (await client.get("/api/v1/tasks?search=%25", headers=h)).json()[
        "total"
    ] == 0
    assert (await client.get("/api/v1/tasks?search=Eski", headers=h)).json()[
        "total"
    ] == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "   "},
        {"title": "x", "priority": "bad"},
        {"title": "x", "status": "bad"},
        {"title": "x", "club_id": str(uuid.uuid4())},
    ],
)
async def test_invalid_create(client, test_club, test_user, payload):
    assert (
        await client.post(
            "/api/v1/tasks", headers=headers(test_user, test_club), json=payload
        )
    ).status_code == 422


async def test_null_update_denied(client, db_session, test_club, test_user):
    task = Task(club_id=test_club.id, title="Başlık")
    db_session.add(task)
    await db_session.flush()
    for key in ("title", "priority", "status"):
        assert (
            await client.patch(
                f"/api/v1/tasks/{task.id}",
                headers=headers(test_user, test_club),
                json={key: None},
            )
        ).status_code == 422


@pytest.mark.parametrize("role", ["veli", "sporcu", "uye", "misafir"])
async def test_unrelated_roles_denied(client, test_club, test_user, role):
    test_user.role = role
    assert (
        await client.get("/api/v1/tasks", headers=headers(test_user, test_club))
    ).status_code == 403


async def test_board_read_only(client, db_session, test_club, test_user):
    task = Task(club_id=test_club.id, title="Yönetim okur")
    db_session.add(task)
    await db_session.flush()
    test_user.role = "baskan"
    h = headers(test_user, test_club)
    assert (await client.get("/api/v1/tasks", headers=h)).json()["total"] == 1
    assert (
        await client.patch(
            f"/api/v1/tasks/{task.id}", headers=h, json={"status": "tamamlandi"}
        )
    ).status_code == 403
    assert (
        await client.delete(f"/api/v1/tasks/{task.id}", headers=h)
    ).status_code == 403
