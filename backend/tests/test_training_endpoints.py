"""Training API testleri — P0-1 (yoklama) ve P0-2 (çoklu antrenör).

Test kapsamı:
  P0-1 (Yoklama):
    - Aktif enrollment → yoklama listesinde görünür
    - Attendance kaydı olmayan katılımcı → görünür, durum boş
    - İptal enrollment → katılımcı listesinde görünmez
    - Başka kursun katılımcısına yoklama yazılamaz (422)

  P0-2 (Çoklu Antrenör):
    - Kursa iki antrenör atanabilir
    - Duplicate atamanın engellenmesi (409 veya 422)
    - antrenor rolü olmayan kişinin reddedilmesi (422)
    - Başka kulüpten kişinin reddedilmesi (422)
    - Mevcut tekil antrenörün güncelleme sonrası junction'da korunması
    - Oturuma birden fazla antrenör
    - Liste/detay çıktılarında instructors alanı
"""
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.club import Club
from app.models.person import Person, PersonRole
from app.models.training import (
    TrainingAttendance,
    TrainingCourse,
    TrainingEnrollment,
    TrainingSession,
)
from app.models.user import User

pytestmark = pytest.mark.asyncio

TRAININGS_URL = "/api/v1/trainings"


# ─── Yardımcılar ──────────────────────────────────────────────────────────────

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _make_person(
    db: AsyncSession,
    club: Club,
    *,
    first_name: str = "Test",
    last_name: str = "Kişi",
    role_codes: list[str] | None = None,
    is_active: bool = True,
) -> Person:
    person = Person(
        id=uuid.uuid4(),
        club_id=club.id,
        first_name=first_name,
        last_name=last_name,
        email=f"p-{uuid.uuid4().hex[:8]}@test.com",
        is_active=is_active,
        is_deleted=False,
    )
    db.add(person)
    await db.flush()
    for code in (role_codes or []):
        db.add(PersonRole(person_id=person.id, role_code=code))
    await db.flush()
    return person


async def _make_course(db: AsyncSession, club: Club, name: str = "Kurs") -> TrainingCourse:
    course = TrainingCourse(
        id=uuid.uuid4(),
        club_id=club.id,
        name=name,
        capacity=0,
        fee=0,
        status="aktif",
    )
    db.add(course)
    await db.flush()
    return course


async def _make_session(
    db: AsyncSession, club: Club, course: TrainingCourse
) -> TrainingSession:
    from datetime import date
    session = TrainingSession(
        id=uuid.uuid4(),
        club_id=club.id,
        course_id=course.id,
        session_date=date(2026, 8, 19),
        status="planli",
    )
    db.add(session)
    await db.flush()
    return session


async def _enroll(
    db: AsyncSession, club: Club, course: TrainingCourse, person: Person, status: str = "active"
) -> TrainingEnrollment:
    enrollment = TrainingEnrollment(
        id=uuid.uuid4(),
        club_id=club.id,
        course_id=course.id,
        person_id=person.id,
        status=status,
    )
    db.add(enrollment)
    await db.flush()
    return enrollment


def _yonetici_token(club: Club, user: User) -> str:
    return create_access_token(str(user.id), str(club.id), user.role)


# ─── P0-1: Yoklama Testleri ───────────────────────────────────────────────────

async def test_p01_active_enrollment_shows_in_participants(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """Aktif enrollment → participants listesinde görünür."""
    sporcu = await _make_person(db_session, test_club, first_name="Aktif", last_name="Sporcu")
    course = await _make_course(db_session, test_club)
    await _enroll(db_session, test_club, course, sporcu, status="active")

    resp = await client.get(
        f"{TRAININGS_URL}/{course.id}/participants",
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    person_ids = [e["person_id"] for e in data]
    assert str(sporcu.id) in person_ids


async def test_p01_no_attendance_record_participant_visible(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """Attendance kaydı olmayan aktif katılımcı → participants'ta görünür, status None."""
    sporcu = await _make_person(db_session, test_club, first_name="Yoklama", last_name="Yok")
    course = await _make_course(db_session, test_club)
    session = await _make_session(db_session, test_club, course)
    await _enroll(db_session, test_club, course, sporcu)

    # Katılımcılar görünmeli
    resp = await client.get(
        f"{TRAININGS_URL}/{course.id}/participants",
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(e["person_id"] == str(sporcu.id) for e in data)

    # Yoklama kaydı yok → attendance listesi boş
    resp2 = await client.get(
        f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/attendance",
        headers=_headers(yonetici_token),
    )
    assert resp2.status_code == 200
    att_data = resp2.json()
    assert not any(a["person_id"] == str(sporcu.id) for a in att_data)


async def test_p01_cancelled_enrollment_not_in_participants(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """İptal enrollment → participants listesinde GÖRÜNMEZ."""
    sporcu = await _make_person(db_session, test_club, first_name="İptal", last_name="Sporcu")
    course = await _make_course(db_session, test_club)
    await _enroll(db_session, test_club, course, sporcu, status="cancelled")

    resp = await client.get(
        f"{TRAININGS_URL}/{course.id}/participants",
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    person_ids = [e["person_id"] for e in data]
    assert str(sporcu.id) not in person_ids


async def test_p01_attendance_rejected_for_non_enrolled_person(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """Başka kursun katılımcısına / kayıtsız kişiye yoklama yazılamaz → 422."""
    sporcu = await _make_person(db_session, test_club, first_name="Dışarıdan", last_name="Kişi")
    course_a = await _make_course(db_session, test_club, name="Kurs A")
    course_b = await _make_course(db_session, test_club, name="Kurs B")
    session_a = await _make_session(db_session, test_club, course_a)
    # sporcu sadece course_b'ye kayıtlı
    await _enroll(db_session, test_club, course_b, sporcu)

    resp = await client.put(
        f"{TRAININGS_URL}/{course_a.id}/sessions/{session_a.id}/attendance",
        json={"records": [{"person_id": str(sporcu.id), "status": "var"}]},
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 422, resp.text


async def test_p01_bulk_attendance_upsert_for_enrolled(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """Aktif kayıtlı kişi için yoklama yazılabilir + iki kez yazılabilir (upsert)."""
    sporcu = await _make_person(db_session, test_club, first_name="Kayıtlı", last_name="Sporcu")
    course = await _make_course(db_session, test_club)
    session = await _make_session(db_session, test_club, course)
    await _enroll(db_session, test_club, course, sporcu)

    # İlk kayıt
    resp = await client.put(
        f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/attendance",
        json={"records": [{"person_id": str(sporcu.id), "status": "var"}]},
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 200
    assert resp.json()["created"] == 1

    # Güncelleme
    resp2 = await client.put(
        f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/attendance",
        json={"records": [{"person_id": str(sporcu.id), "status": "yok"}]},
        headers=_headers(yonetici_token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["updated"] == 1


# ─── P0-2: Çoklu Antrenör Testleri ───────────────────────────────────────────

async def test_p02_course_two_instructors(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """Kursa iki antrenör atanabilir."""
    a1 = await _make_person(db_session, test_club, first_name="Antrenör", last_name="Bir", role_codes=["antrenor"])
    a2 = await _make_person(db_session, test_club, first_name="Antrenör", last_name="İki", role_codes=["antrenor"])

    resp = await client.post(
        TRAININGS_URL,
        json={
            "name": "Çift Antrenör Kurs",
            "instructor_person_ids": [str(a1.id), str(a2.id)],
        },
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    instructor_ids = [i["id"] for i in data["instructors"]]
    assert str(a1.id) in instructor_ids
    assert str(a2.id) in instructor_ids
    assert len(data["instructors"]) == 2
    # Geriye dönük uyumluluk — ilk antrenör
    assert data["instructor_person_id"] == str(a1.id)
    assert data["instructor_name"] is not None


async def test_p02_course_instructor_update_replaces_all(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """PATCH ile instructor_person_ids → tüm antrenörler değiştirilir."""
    a1 = await _make_person(db_session, test_club, first_name="Eski", last_name="Antrenör", role_codes=["antrenor"])
    a2 = await _make_person(db_session, test_club, first_name="Yeni", last_name="Antrenör", role_codes=["antrenor"])

    create_resp = await client.post(
        TRAININGS_URL,
        json={"name": "Güncelleme Kursu", "instructor_person_ids": [str(a1.id)]},
        headers=_headers(yonetici_token),
    )
    assert create_resp.status_code == 201
    course_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"{TRAININGS_URL}/{course_id}",
        json={"instructor_person_ids": [str(a2.id)]},
        headers=_headers(yonetici_token),
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    ids = [i["id"] for i in data["instructors"]]
    assert str(a1.id) not in ids
    assert str(a2.id) in ids


async def test_p02_non_antrenor_role_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """antrenor rolü olmayan kişi → 422."""
    sporcu = await _make_person(db_session, test_club, first_name="Sporcu", last_name="Değil", role_codes=["sporcu"])

    resp = await client.post(
        TRAININGS_URL,
        json={"name": "Hata Kursu", "instructor_person_ids": [str(sporcu.id)]},
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 422, resp.text


async def test_p02_other_club_person_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """Başka kulüpten kişi → 422."""
    # Farklı kulüp oluştur
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

    outsider = await _make_person(db_session, other_club, first_name="Dışarı", last_name="dan", role_codes=["antrenor"])

    resp = await client.post(
        TRAININGS_URL,
        json={"name": "Yabancı Antrenör", "instructor_person_ids": [str(outsider.id)]},
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 422, resp.text


async def test_p02_session_two_instructors(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """Oturuma iki antrenör atanabilir."""
    a1 = await _make_person(db_session, test_club, first_name="Ses", last_name="Bir", role_codes=["antrenor"])
    a2 = await _make_person(db_session, test_club, first_name="Ses", last_name="İki", role_codes=["antrenor"])

    # Kurs oluştur
    create_resp = await client.post(
        TRAININGS_URL,
        json={"name": "Oturum Antrenör Kurs"},
        headers=_headers(yonetici_token),
    )
    assert create_resp.status_code == 201
    course_id = create_resp.json()["id"]

    # Oturum oluştur
    sess_resp = await client.post(
        f"{TRAININGS_URL}/{course_id}/sessions",
        json={
            "session_date": "2026-09-01",
            "instructor_person_ids": [str(a1.id), str(a2.id)],
        },
        headers=_headers(yonetici_token),
    )
    assert sess_resp.status_code == 201, sess_resp.text
    sess_data = sess_resp.json()
    assert len(sess_data["instructors"]) == 2
    ids = [i["id"] for i in sess_data["instructors"]]
    assert str(a1.id) in ids
    assert str(a2.id) in ids


async def test_p02_duplicate_instructor_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """Aynı kişiyi iki kez gönderme — giriş listesi, arka uç aynı kişiyi tekrar eklememeli."""
    a1 = await _make_person(db_session, test_club, first_name="Tekrar", last_name="Antrenör", role_codes=["antrenor"])

    resp = await client.post(
        TRAININGS_URL,
        json={
            "name": "Duplicate Test",
            # Aynı ID iki kez gönderilirse de sadece bir junction satırı oluşmalı
            "instructor_person_ids": [str(a1.id), str(a1.id)],
        },
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    # Sadece bir antrenör görünmeli
    assert len(data["instructors"]) == 1


async def test_p02_instructors_in_list_and_detail(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """Liste ve detay endpoint'lerinde instructors alanı döner."""
    a1 = await _make_person(db_session, test_club, first_name="Liste", last_name="Antrenör", role_codes=["antrenor"])

    create_resp = await client.post(
        TRAININGS_URL,
        json={"name": "Liste Detay Kurs", "instructor_person_ids": [str(a1.id)]},
        headers=_headers(yonetici_token),
    )
    assert create_resp.status_code == 201
    course_id = create_resp.json()["id"]

    # Detay
    detail_resp = await client.get(
        f"{TRAININGS_URL}/{course_id}",
        headers=_headers(yonetici_token),
    )
    assert detail_resp.status_code == 200
    assert len(detail_resp.json()["instructors"]) == 1
    assert detail_resp.json()["instructors"][0]["id"] == str(a1.id)

    # Liste
    list_resp = await client.get(TRAININGS_URL, headers=_headers(yonetici_token))
    assert list_resp.status_code == 200
    course_in_list = next(
        (c for c in list_resp.json()["items"] if c["id"] == course_id), None
    )
    assert course_in_list is not None
    assert len(course_in_list["instructors"]) >= 1


async def test_p02_legacy_instructor_person_id_compat(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """Eski instructor_person_id alanıyla gelen istek junction'a yazılır + geri döner."""
    a1 = await _make_person(db_session, test_club, first_name="Eski", last_name="API", role_codes=["antrenor"])

    resp = await client.post(
        TRAININGS_URL,
        json={"name": "Eski API Kursu", "instructor_person_id": str(a1.id)},
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    # Hem yeni hem eski alanlar dolu olmalı
    assert data["instructor_person_id"] == str(a1.id)
    assert data["instructor_name"] is not None
    assert len(data["instructors"]) == 1
    assert data["instructors"][0]["id"] == str(a1.id)
