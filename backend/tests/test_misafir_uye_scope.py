"""Misafir ve Üye RBAC edge-case testleri.

İzin matrisi:
  misafir: rezervasyon:read, takvim:read
  uye:     rezervasyon:*:own, profil:*:own, takvim:read

Senaryolar:
  - Kısıtlı endpoint'ler → 403
  - UUID manipülasyonu ile kısıtlı kaynağa erişim → 403
  - Takvim/dashboard → açık (takvim:read gerekmez, auth yeterli)
  - Üye kendi person kaydını GET /persons/{id} ile göremez (kisi:read yok)
  - Üye notifications listesini göremez (kulup:read yok)
  - Misafir tüm kısıtlı endpoint'lerde 403 alır
  - Yönetici erişimi bozulmaz
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.club import Club
from app.models.person import Person, PersonRole
from app.models.training import TrainingCourse, TrainingEnrollment, TrainingSession
from app.models.user import User

pytestmark = pytest.mark.asyncio


# ─── Yardımcılar ──────────────────────────────────────────────────────────────

def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token(user: User, club: Club) -> str:
    return create_access_token(str(user.id), str(club.id), user.role)


async def _mk_user(
    db: AsyncSession, club: Club, role: str, person: Person | None = None
) -> User:
    u = User(
        id=uuid.uuid4(),
        club_id=club.id,
        email=f"u-{uuid.uuid4().hex[:8]}@test.com",
        password_hash="x",
        full_name="Test",
        role=role,
        is_active=True,
        is_deleted=False,
        person_id=person.id if person else None,
    )
    db.add(u)
    await db.flush()
    return u


async def _mk_person(db: AsyncSession, club: Club, first: str = "P", last: str = "K") -> Person:
    p = Person(
        id=uuid.uuid4(),
        club_id=club.id,
        first_name=first,
        last_name=last,
        email=f"p-{uuid.uuid4().hex[:8]}@test.com",
        is_active=True,
        is_deleted=False,
    )
    db.add(p)
    await db.flush()
    return p


async def _mk_course(db: AsyncSession, club: Club) -> TrainingCourse:
    c = TrainingCourse(
        id=uuid.uuid4(),
        club_id=club.id,
        name=f"Kurs-{uuid.uuid4().hex[:4]}",
        capacity=0,
        fee=0,
        status="aktif",
    )
    db.add(c)
    await db.flush()
    return c


# ─── Kısıtlı endpoint matrisi ─────────────────────────────────────────────────

_RESTRICTED = [
    ("GET",    "/api/v1/trainings",              "egitim:read"),
    ("GET",    "/api/v1/payments",               "odeme:read"),
    ("GET",    "/api/v1/persons",                "kisi:read"),
    ("GET",    "/api/v1/documents",              "belge:read"),
    ("GET",    "/api/v1/notifications",          "kulup:read"),
    ("GET",    "/api/v1/audit-logs",             "kullanici:read"),
    ("GET",    "/api/v1/users",                  "kullanici:read"),
]


@pytest.mark.parametrize("method,url,perm", _RESTRICTED)
async def test_misafir_forbidden_on_restricted_endpoints(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    method: str,
    url: str,
    perm: str,
) -> None:
    """Misafir kısıtlı endpoint'lerde 403 alır."""
    user = await _mk_user(db_session, test_club, role="misafir")
    token = _token(user, test_club)
    resp = await client.request(method, url, headers=_h(token))
    assert resp.status_code == 403, f"Misafir {url} → {resp.status_code}, beklenen 403 ({perm})"


@pytest.mark.parametrize("method,url,perm", _RESTRICTED)
async def test_uye_forbidden_on_restricted_endpoints(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    method: str,
    url: str,
    perm: str,
) -> None:
    """Üye kısıtlı endpoint'lerde 403 alır."""
    user = await _mk_user(db_session, test_club, role="uye")
    token = _token(user, test_club)
    resp = await client.request(method, url, headers=_h(token))
    assert resp.status_code == 403, f"Üye {url} → {resp.status_code}, beklenen 403 ({perm})"


# ─── UUID manipülasyonu ───────────────────────────────────────────────────────

async def test_misafir_cannot_access_course_by_uuid(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Misafir URL'ye kurs UUID'si girerek kurs detayına erişemez."""
    course = await _mk_course(db_session, test_club)
    user = await _mk_user(db_session, test_club, role="misafir")
    token = _token(user, test_club)

    resp = await client.get(f"/api/v1/trainings/{course.id}", headers=_h(token))
    assert resp.status_code == 403


async def test_uye_cannot_access_course_by_uuid(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Üye URL'ye kurs UUID'si girerek kurs detayına erişemez."""
    course = await _mk_course(db_session, test_club)
    user = await _mk_user(db_session, test_club, role="uye")
    token = _token(user, test_club)

    resp = await client.get(f"/api/v1/trainings/{course.id}", headers=_h(token))
    assert resp.status_code == 403


async def test_misafir_cannot_access_person_by_uuid(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Misafir URL'ye kişi UUID'si girerek kişi profiline erişemez."""
    person = await _mk_person(db_session, test_club)
    user = await _mk_user(db_session, test_club, role="misafir")
    token = _token(user, test_club)

    resp = await client.get(f"/api/v1/persons/{person.id}", headers=_h(token))
    assert resp.status_code == 403


async def test_uye_cannot_access_other_persons_profile(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Üye başka bir kişinin profiline kisi:read olmadığı için erişemez."""
    other_person = await _mk_person(db_session, test_club, first="Başka", last="Kişi")
    uye_person = await _mk_person(db_session, test_club, first="Üye", last="Kişi")
    user = await _mk_user(db_session, test_club, role="uye", person=uye_person)
    token = _token(user, test_club)

    # kendi person_id değil, başkasının → 403
    resp = await client.get(f"/api/v1/persons/{other_person.id}", headers=_h(token))
    assert resp.status_code == 403


async def test_misafir_cannot_write_attendance(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Misafir yoklama yazma endpoint'ine erişemez."""
    course = await _mk_course(db_session, test_club)
    session = TrainingSession(
        id=uuid.uuid4(),
        club_id=test_club.id,
        course_id=course.id,
        session_date=__import__("datetime").date.today(),
        status="planli",
    )
    db_session.add(session)
    await db_session.flush()

    user = await _mk_user(db_session, test_club, role="misafir")
    token = _token(user, test_club)

    resp = await client.put(
        f"/api/v1/trainings/{course.id}/sessions/{session.id}/attendance",
        json={"records": []},
        headers=_h(token),
    )
    assert resp.status_code == 403


async def test_uye_cannot_write_attendance(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Üye yoklama yazma endpoint'ine erişemez."""
    course = await _mk_course(db_session, test_club)
    session = TrainingSession(
        id=uuid.uuid4(),
        club_id=test_club.id,
        course_id=course.id,
        session_date=__import__("datetime").date.today(),
        status="planli",
    )
    db_session.add(session)
    await db_session.flush()

    user = await _mk_user(db_session, test_club, role="uye")
    token = _token(user, test_club)

    resp = await client.put(
        f"/api/v1/trainings/{course.id}/sessions/{session.id}/attendance",
        json={"records": []},
        headers=_h(token),
    )
    assert resp.status_code == 403


# ─── Açık endpoint'ler ────────────────────────────────────────────────────────

async def test_misafir_can_access_calendar(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Misafir takvim endpoint'ine (kimlik doğrulama yeterli) erişebilir."""
    user = await _mk_user(db_session, test_club, role="misafir")
    token = _token(user, test_club)

    resp = await client.get("/api/v1/calendar", headers=_h(token))
    # 200 veya 422 (query param eksik) — ikisi de 403 değil
    assert resp.status_code != 403


async def test_uye_can_access_calendar(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Üye takvim endpoint'ine erişebilir."""
    user = await _mk_user(db_session, test_club, role="uye")
    token = _token(user, test_club)

    resp = await client.get("/api/v1/calendar", headers=_h(token))
    assert resp.status_code != 403


# ─── Başka kulüp verisi erişimi engellenir ────────────────────────────────────

async def test_misafir_cross_club_course_blocked(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Misafir başka bir kulübün kursuna UUID ile erişemez."""
    other_club = Club(
        id=uuid.uuid4(),
        slug=f"other-{uuid.uuid4().hex[:6]}",
        name="Diğer Kulüp",
        plan="starter",
        is_active=True,
        settings={},
    )
    db_session.add(other_club)
    await db_session.flush()

    other_course = TrainingCourse(
        id=uuid.uuid4(),
        club_id=other_club.id,
        name="Diğer Kulüp Kursu",
        capacity=0,
        fee=0,
        status="aktif",
    )
    db_session.add(other_course)
    await db_session.flush()

    # Misafir kendi kulübüne ait token ile diğer kulübün kursuna eriş
    user = await _mk_user(db_session, test_club, role="misafir")
    token = _token(user, test_club)

    # Önce egitim:read yoksa 403; tenant izolasyonu için 403 veya 404 her ikisi de kabul
    resp = await client.get(f"/api/v1/trainings/{other_course.id}", headers=_h(token))
    assert resp.status_code in (403, 404)


# ─── Yönetici geriye dönük bozulmaz ──────────────────────────────────────────

async def test_yonetici_unaffected_by_misafir_uye_changes(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """kulup_yonetici misafir/üye kısıtlamalarından etkilenmez."""
    course = await _mk_course(db_session, test_club)

    resp = await client.get(
        f"/api/v1/trainings/{course.id}", headers=_h(yonetici_token)
    )
    assert resp.status_code == 200

    resp2 = await client.get("/api/v1/persons", headers=_h(yonetici_token))
    assert resp2.status_code == 200
