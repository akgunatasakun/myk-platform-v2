"""P1 Antrenör Scope Testleri.

Test senaryoları:
  - Atandığı kurs görünür
  - Atanmadığı aynı kulüp kursu görünmez (403)
  - Başka kulüp kursu görünmez
  - Sadece oturuma atanmışsa kurs görünür (session-level assignment)
  - Yalnızca atandığı kursun yoklamasını yazabilir
  - Atanmadığı kursa yoklama yazamaz (403)
  - Tüm persons listesi sızmaz
  - Atandığı kursun sporcusunu GET /persons/{id} ile görebilir
  - Atanmadığı kursun sporcusunu göremez (403)
  - Hassas alanlar maskelenir
  - User.person_id bağlantısı olmayan antrenör 403 alır
  - Yönetici (kulup_yonetici) erişimi geriye dönük bozulmaz
"""
import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.club import Club
from app.models.person import Person, PersonRole
from app.models.training import (
    TrainingCourse,
    TrainingCourseInstructor,
    TrainingEnrollment,
    TrainingSession,
    TrainingSessionInstructor,
)
from app.models.user import User

pytestmark = pytest.mark.asyncio

TRAININGS_URL = "/api/v1/trainings"
PERSONS_URL = "/api/v1/persons"


# ─── Yardımcılar ──────────────────────────────────────────────────────────────

def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token(user: User, club: Club) -> str:
    return create_access_token(str(user.id), str(club.id), user.role)


async def _person(
    db: AsyncSession,
    club: Club,
    first_name: str = "Test",
    last_name: str = "Kişi",
    role_codes: list[str] | None = None,
) -> Person:
    p = Person(
        id=uuid.uuid4(),
        club_id=club.id,
        first_name=first_name,
        last_name=last_name,
        email=f"p-{uuid.uuid4().hex[:8]}@test.com",
        is_active=True,
        is_deleted=False,
    )
    db.add(p)
    await db.flush()
    for code in (role_codes or []):
        db.add(PersonRole(person_id=p.id, role_code=code))
    await db.flush()
    return p


async def _user(
    db: AsyncSession,
    club: Club,
    role: str = "antrenor",
    person: Person | None = None,
) -> User:
    u = User(
        id=uuid.uuid4(),
        club_id=club.id,
        email=f"u-{uuid.uuid4().hex[:8]}@test.com",
        password_hash="x",
        full_name="Test User",
        role=role,
        is_active=True,
        is_deleted=False,
        person_id=person.id if person else None,
    )
    db.add(u)
    await db.flush()
    return u


async def _course(db: AsyncSession, club: Club, name: str = "Kurs") -> TrainingCourse:
    c = TrainingCourse(
        id=uuid.uuid4(),
        club_id=club.id,
        name=name,
        capacity=0,
        fee=0,
        status="aktif",
    )
    db.add(c)
    await db.flush()
    return c


async def _session(db: AsyncSession, club: Club, course: TrainingCourse) -> TrainingSession:
    s = TrainingSession(
        id=uuid.uuid4(),
        club_id=club.id,
        course_id=course.id,
        session_date=date.today(),
        status="planli",
    )
    db.add(s)
    await db.flush()
    return s


async def _enroll(
    db: AsyncSession,
    club: Club,
    course: TrainingCourse,
    person: Person,
    status: str = "active",
) -> TrainingEnrollment:
    e = TrainingEnrollment(
        id=uuid.uuid4(),
        club_id=club.id,
        course_id=course.id,
        person_id=person.id,
        status=status,
    )
    db.add(e)
    await db.flush()
    return e


async def _assign_course_instructor(
    db: AsyncSession, club: Club, course: TrainingCourse, person: Person
) -> None:
    db.add(TrainingCourseInstructor(
        id=uuid.uuid4(),
        club_id=club.id,
        course_id=course.id,
        person_id=person.id,
    ))
    await db.flush()


async def _assign_session_instructor(
    db: AsyncSession, club: Club, session: TrainingSession, person: Person
) -> None:
    db.add(TrainingSessionInstructor(
        id=uuid.uuid4(),
        club_id=club.id,
        session_id=session.id,
        person_id=person.id,
    ))
    await db.flush()


# ─── List courses ──────────────────────────────────────────────────────────────

async def test_antrenor_sees_assigned_course(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Antrenör kurs düzeyinde atandığı kursu listede görür."""
    antrenor_person = await _person(db_session, test_club, first_name="Antrenör", last_name="A")
    antrenor_user = await _user(db_session, test_club, role="antrenor", person=antrenor_person)
    course = await _course(db_session, test_club, name="Atanmış Kurs")
    await _assign_course_instructor(db_session, test_club, course, antrenor_person)
    token = _token(antrenor_user, test_club)

    resp = await client.get(f"{TRAININGS_URL}?active_only=false", headers=_h(token))
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()["items"]]
    assert str(course.id) in ids


async def test_antrenor_cannot_see_unassigned_course(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Antrenör atanmadığı aynı kulüp kursunu listede göremez."""
    antrenor_person = await _person(db_session, test_club, first_name="Antrenör", last_name="B")
    antrenor_user = await _user(db_session, test_club, role="antrenor", person=antrenor_person)
    unassigned = await _course(db_session, test_club, name="Atanmamış Kurs")
    token = _token(antrenor_user, test_club)

    resp = await client.get(f"{TRAININGS_URL}?active_only=false", headers=_h(token))
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()["items"]]
    assert str(unassigned.id) not in ids


async def test_antrenor_sees_course_via_session_assignment(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Antrenör sadece bir oturumuna atandığı kursu da listede görür."""
    antrenor_person = await _person(db_session, test_club, first_name="Antrenör", last_name="C")
    antrenor_user = await _user(db_session, test_club, role="antrenor", person=antrenor_person)
    course = await _course(db_session, test_club, name="Oturum Atama Kursu")
    sess = await _session(db_session, test_club, course)
    await _assign_session_instructor(db_session, test_club, sess, antrenor_person)
    token = _token(antrenor_user, test_club)

    resp = await client.get(f"{TRAININGS_URL}?active_only=false", headers=_h(token))
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()["items"]]
    assert str(course.id) in ids


# ─── Get course ───────────────────────────────────────────────────────────────

async def test_antrenor_get_assigned_course_ok(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Antrenör atandığı kursu detay olarak görebilir."""
    antrenor_person = await _person(db_session, test_club, first_name="Ant", last_name="D")
    antrenor_user = await _user(db_session, test_club, role="antrenor", person=antrenor_person)
    course = await _course(db_session, test_club, name="Detay Kurs")
    await _assign_course_instructor(db_session, test_club, course, antrenor_person)
    token = _token(antrenor_user, test_club)

    resp = await client.get(f"{TRAININGS_URL}/{course.id}", headers=_h(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == str(course.id)


async def test_antrenor_get_unassigned_course_403(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Antrenör atanmadığı kurs detayına erişemez."""
    antrenor_person = await _person(db_session, test_club, first_name="Ant", last_name="E")
    antrenor_user = await _user(db_session, test_club, role="antrenor", person=antrenor_person)
    course = await _course(db_session, test_club, name="Yasak Kurs")
    token = _token(antrenor_user, test_club)

    resp = await client.get(f"{TRAININGS_URL}/{course.id}", headers=_h(token))
    assert resp.status_code == 403


# ─── Attendance write ─────────────────────────────────────────────────────────

async def test_antrenor_can_write_attendance_for_assigned_course(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Antrenör atandığı kursun oturumuna yoklama yazabilir."""
    antrenor_person = await _person(db_session, test_club, first_name="Ant", last_name="F")
    antrenor_user = await _user(db_session, test_club, role="antrenor", person=antrenor_person)
    sporcu = await _person(db_session, test_club, first_name="Sporcu", last_name="F")
    course = await _course(db_session, test_club, name="Yoklama Kurs")
    sess = await _session(db_session, test_club, course)
    await _assign_course_instructor(db_session, test_club, course, antrenor_person)
    await _enroll(db_session, test_club, course, sporcu)
    token = _token(antrenor_user, test_club)

    payload = {"records": [{"person_id": str(sporcu.id), "status": "var"}]}
    resp = await client.put(
        f"{TRAININGS_URL}/{course.id}/sessions/{sess.id}/attendance",
        json=payload,
        headers=_h(token),
    )
    assert resp.status_code == 200


async def test_antrenor_cannot_write_attendance_for_unassigned_course(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Antrenör atanmadığı kursun oturumuna yoklama yazamaz."""
    antrenor_person = await _person(db_session, test_club, first_name="Ant", last_name="G")
    antrenor_user = await _user(db_session, test_club, role="antrenor", person=antrenor_person)
    sporcu = await _person(db_session, test_club, first_name="Sporcu", last_name="G")
    course = await _course(db_session, test_club, name="Yasak Yoklama Kurs")
    sess = await _session(db_session, test_club, course)
    await _enroll(db_session, test_club, course, sporcu)
    token = _token(antrenor_user, test_club)

    payload = {"records": [{"person_id": str(sporcu.id), "status": "var"}]}
    resp = await client.put(
        f"{TRAININGS_URL}/{course.id}/sessions/{sess.id}/attendance",
        json=payload,
        headers=_h(token),
    )
    assert resp.status_code == 403


# ─── Persons scope ────────────────────────────────────────────────────────────

async def test_antrenor_persons_list_scoped(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Antrenör persons listesinde yalnızca kendi kursunun sporcularını görür."""
    antrenor_person = await _person(db_session, test_club, first_name="Ant", last_name="H")
    antrenor_user = await _user(db_session, test_club, role="antrenor", person=antrenor_person)

    sporcu_in = await _person(db_session, test_club, first_name="Görünen", last_name="Sporcu")
    sporcu_out = await _person(db_session, test_club, first_name="Görünmez", last_name="Sporcu")

    course = await _course(db_session, test_club, name="Scope Kurs")
    await _assign_course_instructor(db_session, test_club, course, antrenor_person)
    await _enroll(db_session, test_club, course, sporcu_in)
    # sporcu_out kurs dışı — enroll yok

    token = _token(antrenor_user, test_club)
    resp = await client.get(PERSONS_URL, headers=_h(token))
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["items"]]
    assert str(sporcu_in.id) in ids
    assert str(sporcu_out.id) not in ids


async def test_antrenor_get_enrolled_person_ok(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Antrenör kendi kursuna kayıtlı sporcunun profilini görebilir."""
    antrenor_person = await _person(db_session, test_club, first_name="Ant", last_name="I")
    antrenor_user = await _user(db_session, test_club, role="antrenor", person=antrenor_person)
    sporcu = await _person(db_session, test_club, first_name="Kayıtlı", last_name="Sporcu")
    course = await _course(db_session, test_club, name="Profil Kurs")
    await _assign_course_instructor(db_session, test_club, course, antrenor_person)
    await _enroll(db_session, test_club, course, sporcu)
    token = _token(antrenor_user, test_club)

    resp = await client.get(f"{PERSONS_URL}/{sporcu.id}", headers=_h(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == str(sporcu.id)


async def test_antrenor_get_unenrolled_person_403(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Antrenör kendi kursuna kayıtlı olmayan kişiyi göremez."""
    antrenor_person = await _person(db_session, test_club, first_name="Ant", last_name="J")
    antrenor_user = await _user(db_session, test_club, role="antrenor", person=antrenor_person)
    outsider = await _person(db_session, test_club, first_name="Dışarıdaki", last_name="Kişi")
    token = _token(antrenor_user, test_club)

    resp = await client.get(f"{PERSONS_URL}/{outsider.id}", headers=_h(token))
    assert resp.status_code == 403


async def test_antrenor_can_see_own_person_record(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Antrenör kendi person kaydını her zaman görebilir."""
    antrenor_person = await _person(db_session, test_club, first_name="Ant", last_name="K")
    antrenor_user = await _user(db_session, test_club, role="antrenor", person=antrenor_person)
    token = _token(antrenor_user, test_club)

    resp = await client.get(f"{PERSONS_URL}/{antrenor_person.id}", headers=_h(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == str(antrenor_person.id)


# ─── Hassas alanlar ───────────────────────────────────────────────────────────

async def test_antrenor_sensitive_fields_masked(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Antrenör hassas alanları (tc_no vb.) maskelenmiş görmeli."""
    antrenor_person = await _person(db_session, test_club, first_name="Ant", last_name="L")
    antrenor_user = await _user(db_session, test_club, role="antrenor", person=antrenor_person)
    sporcu = await _person(db_session, test_club, first_name="Hassas", last_name="Sporcu")
    course = await _course(db_session, test_club, name="Maske Kurs")
    await _assign_course_instructor(db_session, test_club, course, antrenor_person)
    await _enroll(db_session, test_club, course, sporcu)
    token = _token(antrenor_user, test_club)

    resp = await client.get(f"{PERSONS_URL}/{sporcu.id}", headers=_h(token))
    assert resp.status_code == 200
    data = resp.json()
    # Hassas alanlar maskelenmeli ya da "***" olmalı
    for field in ("tc_no", "kan_grubu", "alerji", "ozel_durum", "acil_tel"):
        if field in data and data[field] is not None:
            assert data[field] == "***", f"{field} maskelenmemiş"


# ─── person_id bağlantısı olmayan antrenör ───────────────────────────────────

async def test_antrenor_without_person_id_gets_403(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """User.person_id bağlantısı olmayan antrenör 403 alır."""
    # person_id=None olan antrenör kullanıcı
    antrenor_user = await _user(db_session, test_club, role="antrenor", person=None)
    token = _token(antrenor_user, test_club)

    resp = await client.get(f"{TRAININGS_URL}?active_only=false", headers=_h(token))
    assert resp.status_code == 403


# ─── Yönetici erişimi geriye dönük bozulmuyor ────────────────────────────────

async def test_yonetici_still_sees_all_courses(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """kulup_yonetici tüm kursları görmeye devam eder."""
    course_a = await _course(db_session, test_club, name="Yön Kurs A")
    course_b = await _course(db_session, test_club, name="Yön Kurs B")

    resp = await client.get(f"{TRAININGS_URL}?active_only=false", headers=_h(yonetici_token))
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()["items"]]
    assert str(course_a.id) in ids
    assert str(course_b.id) in ids


async def test_yonetici_still_sees_all_persons(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """kulup_yonetici tüm kişileri görmeye devam eder."""
    p1 = await _person(db_session, test_club, first_name="Yön", last_name="P1")
    p2 = await _person(db_session, test_club, first_name="Yön", last_name="P2")

    resp = await client.get(PERSONS_URL, headers=_h(yonetici_token))
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["items"]]
    assert str(p1.id) in ids
    assert str(p2.id) in ids
