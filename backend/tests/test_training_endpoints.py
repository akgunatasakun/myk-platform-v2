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
from datetime import date, time as t, timedelta

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


# ─── Self Check-in Testleri ───────────────────────────────────────────────────

async def _make_adult_course(db: AsyncSession, club: Club) -> TrainingCourse:
    """adult_self_checkin modlu aktif kurs."""
    course = TrainingCourse(
        id=uuid.uuid4(),
        club_id=club.id,
        name="Yetişkin Self-Check-in Kursu",
        capacity=20,
        fee=0,
        status="aktif",
        attendance_mode="adult_self_checkin",
    )
    db.add(course)
    await db.flush()
    return course


async def _make_adult_sporcu(
    db: AsyncSession,
    club: Club,
    *,
    birth_date: date | None = None,
) -> tuple[Person, User]:
    """Person oluştur + person_id bağlı sporcu User döndür."""
    person = Person(
        id=uuid.uuid4(),
        club_id=club.id,
        first_name="Self",
        last_name="Sporcu",
        email=f"self-{uuid.uuid4().hex[:8]}@test.com",
        birth_date=birth_date,
        is_active=True,
        is_deleted=False,
    )
    db.add(person)
    await db.flush()

    user = User(
        id=uuid.uuid4(),
        club_id=club.id,
        email=f"self-u-{uuid.uuid4().hex[:8]}@test.com",
        password_hash="x",
        full_name="Self Sporcu",
        role="sporcu",
        is_active=True,
        is_deleted=False,
        person_id=person.id,
    )
    db.add(user)
    await db.flush()
    return person, user


async def test_self_checkin_success(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Geçerli self-check-in 200 döner ve 'var' kaydı oluşturulur."""
    course = await _make_adult_course(db_session, test_club)
    session = await _make_session(db_session, test_club, course)
    person, user = await _make_adult_sporcu(
        db_session, test_club, birth_date=date(2000, 1, 1)
    )
    await _enroll(db_session, test_club, course, person)

    token = create_access_token(str(user.id), str(test_club.id), user.role)
    url = f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/self-checkin"

    resp = await client.post(url, headers=_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "var"
    assert data["person_id"] == str(person.id)
    assert data["session_id"] == str(session.id)


async def test_self_checkin_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Aynı sporcu aynı oturuma iki kez check-in yaparsa mevcut kayıt döner (idempotent)."""
    course = await _make_adult_course(db_session, test_club)
    session = await _make_session(db_session, test_club, course)
    person, user = await _make_adult_sporcu(
        db_session, test_club, birth_date=date(2000, 1, 1)
    )
    await _enroll(db_session, test_club, course, person)

    token = create_access_token(str(user.id), str(test_club.id), user.role)
    url = f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/self-checkin"

    r1 = await client.post(url, headers=_headers(token))
    r2 = await client.post(url, headers=_headers(token))
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Aynı kayıt dönmeli
    assert r1.json()["id"] == r2.json()["id"]


async def test_self_checkin_under_18_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """18 yaş altı sporcu self-check-in yapamaz (403)."""
    course = await _make_adult_course(db_session, test_club)
    session = await _make_session(db_session, test_club, course)
    # Oturum tarihi 2026-08-19; 2010-01-01 doğumlu → 16 yaşında
    person, user = await _make_adult_sporcu(
        db_session, test_club, birth_date=date(2010, 1, 1)
    )
    await _enroll(db_session, test_club, course, person)

    token = create_access_token(str(user.id), str(test_club.id), user.role)
    url = f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/self-checkin"

    resp = await client.post(url, headers=_headers(token))
    assert resp.status_code == 403
    assert "18" in resp.json()["detail"]


async def test_self_checkin_wrong_mode_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """coach_daily modlu kursa self-check-in 403 döner."""
    course = await _make_course(db_session, test_club, name="Antrenör Modu Kurs")
    # attendance_mode varsayılan: coach_daily
    session = await _make_session(db_session, test_club, course)
    person, user = await _make_adult_sporcu(
        db_session, test_club, birth_date=date(1995, 1, 1)
    )
    await _enroll(db_session, test_club, course, person)

    token = create_access_token(str(user.id), str(test_club.id), user.role)
    url = f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/self-checkin"

    resp = await client.post(url, headers=_headers(token))
    assert resp.status_code == 403
    assert "self check-in" in resp.json()["detail"].lower()


async def test_self_checkin_not_enrolled_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Kayıtlı olmayan sporcu self-check-in yapamaz (403)."""
    course = await _make_adult_course(db_session, test_club)
    session = await _make_session(db_session, test_club, course)
    person, user = await _make_adult_sporcu(
        db_session, test_club, birth_date=date(1995, 1, 1)
    )
    # Enrollment yok — enroll() çağrılmadı

    token = create_access_token(str(user.id), str(test_club.id), user.role)
    url = f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/self-checkin"

    resp = await client.post(url, headers=_headers(token))
    assert resp.status_code == 403
    assert "kayıtlı" in resp.json()["detail"]


async def test_self_checkin_user_without_person_id_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    sporcu_user: User,
    sporcu_token: str,
) -> None:
    """person_id bağlantısı olmayan kullanıcı self-check-in yapamaz (403)."""
    # sporcu_user'ın person_id'si None (conftest'te set edilmiyor)
    course = await _make_adult_course(db_session, test_club)
    session = await _make_session(db_session, test_club, course)

    url = f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/self-checkin"
    resp = await client.post(url, headers=_headers(sporcu_token))
    assert resp.status_code == 403
    assert "sporcu kaydına bağlı" in resp.json()["detail"]


async def test_self_checkin_tenant_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Başka kulübün sporcusu self-check-in yapamaz (403)."""
    # Farklı kulüp
    other_club = Club(
        id=uuid.uuid4(),
        slug=f"other-{uuid.uuid4().hex[:8]}",
        name="Diğer Kulüp",
        plan="starter",
        is_active=True,
        settings={},
    )
    db_session.add(other_club)
    await db_session.flush()

    # Ana kulüp kursu
    course = await _make_adult_course(db_session, test_club)
    session = await _make_session(db_session, test_club, course)

    # Diğer kulübün kişisi
    other_person = Person(
        id=uuid.uuid4(),
        club_id=other_club.id,
        first_name="Diğer",
        last_name="Sporcu",
        email=f"other-{uuid.uuid4().hex[:8]}@test.com",
        birth_date=date(1995, 1, 1),
        is_active=True,
        is_deleted=False,
    )
    db_session.add(other_person)
    await db_session.flush()

    other_user = User(
        id=uuid.uuid4(),
        club_id=test_club.id,   # JWT kulübü ana kulüp (tenant doğru)
        email=f"other-u-{uuid.uuid4().hex[:8]}@test.com",
        password_hash="x",
        full_name="Diğer Sporcu",
        role="sporcu",
        is_active=True,
        is_deleted=False,
        person_id=other_person.id,  # Ama person başka kulüpte
    )
    db_session.add(other_user)
    await db_session.flush()

    token = create_access_token(str(other_user.id), str(test_club.id), other_user.role)
    url = f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/self-checkin"

    resp = await client.post(url, headers=_headers(token))
    assert resp.status_code == 403


async def test_self_checkin_window_closed(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """start_time/end_time set edilmiş ve pencere kapalıysa 403 döner."""
    course = await _make_adult_course(db_session, test_club)

    # Oturum dün sona erdi (pencere kesinlikle kapalı)
    yesterday = date.today() - timedelta(days=1)
    session = TrainingSession(
        id=uuid.uuid4(),
        club_id=test_club.id,
        course_id=course.id,
        session_date=yesterday,
        start_time=t(9, 0),
        end_time=t(10, 0),
        status="tamamlandi",
    )
    db_session.add(session)
    await db_session.flush()

    person, user = await _make_adult_sporcu(
        db_session, test_club, birth_date=date(1995, 1, 1)
    )
    await _enroll(db_session, test_club, course, person)

    token = create_access_token(str(user.id), str(test_club.id), user.role)
    url = f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/self-checkin"

    resp = await client.post(url, headers=_headers(token))
    assert resp.status_code == 403
    assert "pencere" in resp.json()["detail"].lower()


async def test_self_checkin_no_time_window_open_all_day(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """start_time/end_time yoksa tüm gün açık — bugünkü oturum başarılı check-in yapar."""
    course = await _make_adult_course(db_session, test_club)
    # start_time/end_time yok (tüm gün fallback)
    session = TrainingSession(
        id=uuid.uuid4(),
        club_id=test_club.id,
        course_id=course.id,
        session_date=date.today(),
        status="planli",
    )
    db_session.add(session)
    await db_session.flush()

    person, user = await _make_adult_sporcu(
        db_session, test_club, birth_date=date(1995, 1, 1)
    )
    await _enroll(db_session, test_club, course, person)

    token = create_access_token(str(user.id), str(test_club.id), user.role)
    url = f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/self-checkin"

    resp = await client.post(url, headers=_headers(token))
    assert resp.status_code == 200, resp.text


# ─── Ek Sprint-17 Testleri (critical review) ─────────────────────────────────


async def test_self_checkin_no_birth_date_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """birth_date=None → 403, hata mesajı 'doğum tarihi' içermeli."""
    course = await _make_adult_course(db_session, test_club)
    session = TrainingSession(
        id=uuid.uuid4(),
        club_id=test_club.id,
        course_id=course.id,
        session_date=date.today(),
        status="planli",
    )
    db_session.add(session)
    await db_session.flush()

    # birth_date=None (varsayılan) → 403 bekleniyor
    person, user = await _make_adult_sporcu(db_session, test_club)
    await _enroll(db_session, test_club, course, person)

    token = create_access_token(str(user.id), str(test_club.id), user.role)
    url = f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/self-checkin"

    resp = await client.post(url, headers=_headers(token))
    assert resp.status_code == 403, resp.text
    assert "doğum tarihi" in resp.json()["detail"].lower()


async def test_self_checkin_same_day_fallback_yesterday_closed(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Saatsiz oturum dün ise pencere kapalıdır (sadece aynı gün açık)."""
    course = await _make_adult_course(db_session, test_club)
    yesterday = date.today() - timedelta(days=1)
    session = TrainingSession(
        id=uuid.uuid4(),
        club_id=test_club.id,
        course_id=course.id,
        session_date=yesterday,
        status="tamamlandi",
    )
    db_session.add(session)
    await db_session.flush()

    person, user = await _make_adult_sporcu(
        db_session, test_club, birth_date=date(1995, 1, 1)
    )
    await _enroll(db_session, test_club, course, person)

    token = create_access_token(str(user.id), str(test_club.id), user.role)
    url = f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/self-checkin"

    resp = await client.post(url, headers=_headers(token))
    assert resp.status_code == 403, resp.text
    assert "pencere" in resp.json()["detail"].lower()


async def test_self_checkin_sessions_me_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """Sporcu /me/self-checkin-sessions ile kendi adult_self_checkin oturumlarını görür."""
    course = await _make_adult_course(db_session, test_club)
    session = TrainingSession(
        id=uuid.uuid4(),
        club_id=test_club.id,
        course_id=course.id,
        session_date=date.today(),
        status="planli",
    )
    db_session.add(session)
    await db_session.flush()

    person, user = await _make_adult_sporcu(
        db_session, test_club, birth_date=date(1995, 1, 1)
    )
    await _enroll(db_session, test_club, course, person)

    token = create_access_token(str(user.id), str(test_club.id), user.role)
    resp = await client.get(
        f"{TRAININGS_URL}/me/self-checkin-sessions",
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    session_ids = [s["session_id"] for s in data]
    assert str(session.id) in session_ids


async def test_self_checkin_sessions_coach_daily_excluded(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
) -> None:
    """coach_daily modlu kurs /me/self-checkin-sessions listesinde görünmez."""
    course = await _make_course(db_session, test_club, name="Antrenör Modu Kursu")
    # attendance_mode varsayılan coach_daily
    session = TrainingSession(
        id=uuid.uuid4(),
        club_id=test_club.id,
        course_id=course.id,
        session_date=date.today(),
        status="planli",
    )
    db_session.add(session)
    await db_session.flush()

    person, user = await _make_adult_sporcu(
        db_session, test_club, birth_date=date(1995, 1, 1)
    )
    await _enroll(db_session, test_club, course, person)

    token = create_access_token(str(user.id), str(test_club.id), user.role)
    resp = await client.get(
        f"{TRAININGS_URL}/me/self-checkin-sessions",
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    session_ids = [s["session_id"] for s in resp.json()]
    assert str(session.id) not in session_ids


async def test_audit_action_coach_created_on_first_record(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """İlk bulk kayıt → action='training_attendance_coach_created'."""
    import sqlalchemy as sa
    from app.models.audit import AuditLog

    course = await _make_course(db_session, test_club)
    session = await _make_session(db_session, test_club, course)
    person = await _make_person(db_session, test_club, first_name="Audit", last_name="C")
    await _enroll(db_session, test_club, course, person)

    url = f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/attendance"
    resp = await client.put(
        url,
        json={"records": [{"person_id": str(person.id), "status": "var"}]},
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] == 1
    assert resp.json()["updated"] == 0

    q = await db_session.execute(
        sa.select(AuditLog)
        .where(
            AuditLog.club_id == test_club.id,
            AuditLog.resource_type == "training_attendance",
        )
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    log = q.scalar_one_or_none()
    assert log is not None
    assert log.action == "training_attendance_coach_created"


async def test_audit_action_coach_overridden_on_status_change(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """Durum değişikliği → action='training_attendance_coach_overridden', changes.after.overrides dolu."""
    import sqlalchemy as sa
    from app.models.audit import AuditLog

    course = await _make_course(db_session, test_club)
    session = await _make_session(db_session, test_club, course)
    person = await _make_person(db_session, test_club, first_name="Audit", last_name="O")
    await _enroll(db_session, test_club, course, person)

    url = f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/attendance"
    # İlk kayıt: var
    await client.put(
        url,
        json={"records": [{"person_id": str(person.id), "status": "var"}]},
        headers=_headers(yonetici_token),
    )
    # Durum değişikliği: yok (override)
    resp = await client.put(
        url,
        json={"records": [{"person_id": str(person.id), "status": "yok"}]},
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 200, resp.text

    q = await db_session.execute(
        sa.select(AuditLog)
        .where(
            AuditLog.club_id == test_club.id,
            AuditLog.resource_type == "training_attendance",
            AuditLog.action == "training_attendance_coach_overridden",
        )
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    log = q.scalar_one_or_none()
    assert log is not None
    assert log.changes is not None
    assert "overrides" in log.changes.get("after", {})


async def test_audit_action_coach_updated_on_notes_change(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    """Aynı durum, farklı not → action='training_attendance_coach_updated' (override değil)."""
    import sqlalchemy as sa
    from app.models.audit import AuditLog

    course = await _make_course(db_session, test_club)
    session = await _make_session(db_session, test_club, course)
    person = await _make_person(db_session, test_club, first_name="Audit", last_name="U")
    await _enroll(db_session, test_club, course, person)

    url = f"{TRAININGS_URL}/{course.id}/sessions/{session.id}/attendance"
    # İlk kayıt
    await client.put(
        url,
        json={"records": [{"person_id": str(person.id), "status": "var", "notes": "not1"}]},
        headers=_headers(yonetici_token),
    )
    # Aynı durum, not değişikliği
    resp = await client.put(
        url,
        json={"records": [{"person_id": str(person.id), "status": "var", "notes": "not2"}]},
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated"] == 1

    q = await db_session.execute(
        sa.select(AuditLog)
        .where(
            AuditLog.club_id == test_club.id,
            AuditLog.resource_type == "training_attendance",
            AuditLog.action == "training_attendance_coach_updated",
        )
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    log = q.scalar_one_or_none()
    assert log is not None
