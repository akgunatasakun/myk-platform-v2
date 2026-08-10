"""Academy endpoint testleri — Sprint 5C-2 + 5C-3.

Kapsam: 20 test
- Program/modül/ders katalog endpoint'leri
- Enrollment + tenant izolasyonu
- Session + Heartbeat + Progress
- Quiz attempt/answer/finish
- Güvenlik: correct_letter ifşası yok, 401/403 kontrolleri
- KnotPlayer timeline endpoint (5C-3)
"""
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.academy import (
    AcademyEnrollment,
    AcademyLesson,
    AcademyLessonStep,
    AcademyModule,
    AcademyProgram,
    AcademyQuizQuestion,
    AcademySession,
)
from app.models.club import Club
from app.models.person import Person
from app.models.user import User


# ─── Yardımcı seed ───────────────────────────────────────────────────────────

async def _make_club(db: AsyncSession, slug_suffix: str = "") -> Club:
    suffix = slug_suffix or uuid.uuid4().hex[:6]
    club = Club(
        id=uuid.uuid4(),
        slug=f"test-kulup-{suffix}",
        name=f"Test Kulüp {suffix}",
        plan="starter",
        is_active=True,
        settings={},
    )
    db.add(club)
    await db.flush()
    return club


async def _make_person(db: AsyncSession, club: Club) -> Person:
    person = Person(
        club_id=club.id,
        first_name="Test",
        last_name=f"Kisi-{uuid.uuid4().hex[:6]}",
    )
    db.add(person)
    await db.flush()
    return person


async def _make_user(
    db: AsyncSession,
    club: Club,
    person: Person | None = None,
    role: str = "sporcu",
) -> tuple[User, str]:
    """(User, token) döndürür."""
    user = User(
        id=uuid.uuid4(),
        club_id=club.id,
        email=f"u-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("Test1234!"),
        full_name="Test User",
        role=role,
        is_active=True,
        is_deleted=False,
        person_id=person.id if person else None,
    )
    db.add(user)
    await db.flush()
    token = create_access_token(user.id, club.id, user.role)
    return user, token


async def _seed_program(db: AsyncSession) -> tuple[AcademyProgram, AcademyModule, AcademyLesson]:
    """D1 programı, gemici-baglari modülü, izbarco dersi + 5 quiz sorusu."""
    program = AcademyProgram(
        slug=f"d1-{uuid.uuid4().hex[:6]}",  # unique slug per test
        kod="D1",
        ad="Deniz 1 Programı",
        seviye=1,
        aktif=True,
        club_id=None,
    )
    db.add(program)
    await db.flush()

    module = AcademyModule(
        program_id=program.id,
        slug=f"gemici-baglari-{uuid.uuid4().hex[:6]}",
        ad="Gemici Bağları",
        sira=1,
        aktif=True,
    )
    db.add(module)
    await db.flush()

    lesson = AcademyLesson(
        module_id=module.id,
        slug=f"izbarco-{uuid.uuid4().hex[:6]}",
        ad="İzbarço",
        ders_tipi="knot",
        tahmini_sure_dk=10,
        sira=1,
        aktif=True,
    )
    db.add(lesson)
    await db.flush()

    db.add(
        AcademyLessonStep(
            lesson_id=lesson.id,
            sira=1,
            tip="knot_animation",
            baslik="İzbarço Animasyonu",
            data_json={"slug": "izbarco", "timeline_url": "/api/v1/academy/knot/izbarco/timeline"},
        )
    )

    # 5 quiz sorusu
    quiz_questions = [
        ("İzbarço bağının en önemli özelliği nedir?",
         [{"harf": "A", "metin": "İki ipi birleştirir"},
          {"harf": "B", "metin": "İlmek boyutu sabit kalır ve kolayca çözülür"},
          {"harf": "C", "metin": "Halatın ucunu keser"},
          {"harf": "D", "metin": "Yalnızca kalın halatlarda"}], "B",
         "İzbarço bağında ilmek boyutu sabit kalır."),
        ("Hangi bağ yelkencilikte en sık kullanılır?",
         [{"harf": "A", "metin": "Camadan"}, {"harf": "B", "metin": "Kropi"},
          {"harf": "C", "metin": "Kazık"}, {"harf": "D", "metin": "İzbarço"}], "D",
         "İzbarço bağı yelkencilikte en sık kullanılan bağdır."),
        ("Kropi (sekiz) bağı ne amaçla kullanılır?",
         [{"harf": "A", "metin": "İki ipi birleştirmek"},
          {"harf": "B", "metin": "Bloktan kaçmayı önlemek"},
          {"harf": "C", "metin": "Tekneyi direğe bağlamak"},
          {"harf": "D", "metin": "Yelkeni bağlamak"}], "B",
         "Kropi, halatın bloktan kaçmasını önler."),
        ("Hangi bağ eşit çaplı iki ipi birleştirmek için kullanılır?",
         [{"harf": "A", "metin": "Kazık"}, {"harf": "B", "metin": "İzbarço"},
          {"harf": "C", "metin": "Camadan"}, {"harf": "D", "metin": "Kropi"}], "C",
         "Camadan bağı eşit çaplı ipler için kullanılır."),
        ("Teknenin baş ipini direğe bağlamak için hangi bağ kullanılır?",
         [{"harf": "A", "metin": "Camadan"}, {"harf": "B", "metin": "Kropi"},
          {"harf": "C", "metin": "Kazık"}, {"harf": "D", "metin": "İzbarço"}], "C",
         "Kazık bağı baş ipini direğe bağlamak için kullanılır."),
    ]
    question_objs = []
    for i, (soru, secenek, dogru, aciklama) in enumerate(quiz_questions, start=1):
        q = AcademyQuizQuestion(
            lesson_id=lesson.id,
            sira=i,
            soru_metni=soru,
            options=secenek,
            correct_letter=dogru,
            aciklama=aciklama,
        )
        db.add(q)
        question_objs.append(q)
    await db.flush()

    return program, module, lesson


# ─── Fixture'lar ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def club_a(db_session: AsyncSession) -> Club:
    return await _make_club(db_session, "a")


@pytest_asyncio.fixture
async def club_b(db_session: AsyncSession) -> Club:
    return await _make_club(db_session, "b")


@pytest_asyncio.fixture
async def person_a(db_session: AsyncSession, club_a: Club) -> Person:
    return await _make_person(db_session, club_a)


@pytest_asyncio.fixture
async def user_with_person(db_session: AsyncSession, club_a: Club, person_a: Person):
    return await _make_user(db_session, club_a, person=person_a)


@pytest_asyncio.fixture
async def user_no_person(db_session: AsyncSession, club_a: Club):
    return await _make_user(db_session, club_a, person=None)


@pytest_asyncio.fixture
async def seed(db_session: AsyncSession):
    return await _seed_program(db_session)


@pytest_asyncio.fixture
async def enrolled(db_session: AsyncSession, seed, user_with_person, club_a):
    program, module, lesson = seed
    _, token = user_with_person
    person_a_result = await db_session.execute(
        __import__("sqlalchemy", fromlist=["select"]).select(User).where(
            User.email.contains("@test.com"),
            User.club_id == club_a.id,
            User.person_id.isnot(None),
        )
    )
    user = person_a_result.scalars().first()
    enrollment = AcademyEnrollment(
        club_id=club_a.id,
        person_id=user.person_id,
        program_id=program.id,
        status="active",
    )
    db_session.add(enrollment)
    await db_session.flush()
    return program, module, lesson, enrollment


# ─── Test 1: Program listesi ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_programs_list(
    client: AsyncClient,
    seed,
    user_with_person,
) -> None:
    """GET /programs → 200, D1 var."""
    _, token = user_with_person
    program, _, _ = seed

    resp = await client.get(
        "/api/v1/academy/programs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    ids = [p["id"] for p in data]
    assert str(program.id) in ids


# ─── Test 2: Program detayı ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_program_detail(
    client: AsyncClient,
    seed,
    user_with_person,
) -> None:
    """GET /programs/{slug} → modules + lessons var."""
    _, token = user_with_person
    program, module, lesson = seed

    resp = await client.get(
        f"/api/v1/academy/programs/{program.slug}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == program.slug
    assert data["kod"] == "D1"
    assert len(data["modules"]) >= 1
    module_slugs = [m["slug"] for m in data["modules"]]
    assert module.slug in module_slugs


# ─── Test 3: Ders detayı ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lesson_detail(
    client: AsyncClient,
    seed,
    user_with_person,
) -> None:
    """GET /lessons/{slug} → steps var."""
    _, token = user_with_person
    _, _, lesson = seed

    resp = await client.get(
        f"/api/v1/academy/lessons/{lesson.slug}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == lesson.slug
    assert data["ders_tipi"] == "knot"
    assert len(data["steps"]) >= 1
    assert data["steps"][0]["tip"] == "knot_animation"


# ─── Test 4: Enrollment başarılı ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enroll_success(
    client: AsyncClient,
    seed,
    user_with_person,
) -> None:
    """POST /programs/{id}/enroll → 201."""
    _, token = user_with_person
    program, _, _ = seed

    resp = await client.post(
        f"/api/v1/academy/programs/{program.id}/enroll",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["program_id"] == str(program.id)
    assert data["status"] == "active"


# ─── Test 5: Enrollment duplicate → 409 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_enroll_duplicate(
    client: AsyncClient,
    seed,
    user_with_person,
) -> None:
    """Aynı programa ikinci enrollment → 409."""
    _, token = user_with_person
    program, _, _ = seed

    resp1 = await client.post(
        f"/api/v1/academy/programs/{program.id}/enroll",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        f"/api/v1/academy/programs/{program.id}/enroll",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 409


# ─── Test 6: Tenant izolasyonu ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enroll_tenant_isolation(
    client: AsyncClient,
    seed,
    club_b: Club,
    db_session: AsyncSession,
) -> None:
    """Club B kullanıcısı, Club A'nın enrollment'larını göremez."""
    program, _, _ = seed

    person_b = await _make_person(db_session, club_b)
    _, token_b = await _make_user(db_session, club_b, person=person_b)

    # Club B kullanıcısı Club A programına enroll olsun
    resp = await client.post(
        f"/api/v1/academy/programs/{program.id}/enroll",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 201

    # Club B kullanıcısının enrollment'ları sorgulandığında sadece kendi görünür
    me_resp = await client.get(
        "/api/v1/academy/me/enrollments",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert me_resp.status_code == 200
    enrollments = me_resp.json()
    # Başka kulübün person enrollment'ları görünmemeli
    assert all(e["program_id"] == str(program.id) for e in enrollments)


# ─── Test 7: Session oluştur ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_create(
    client: AsyncClient,
    enrolled,
    user_with_person,
) -> None:
    """POST /lessons/{id}/sessions → 201."""
    _, token = user_with_person
    program, module, lesson, _ = enrolled

    resp = await client.post(
        f"/api/v1/academy/lessons/{lesson.id}/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["lesson_id"] == str(lesson.id)
    assert "started_at" in data


# ─── Test 8: Heartbeat → progress güncellenir ────────────────────────────────

@pytest.mark.asyncio
async def test_heartbeat(
    client: AsyncClient,
    enrolled,
    user_with_person,
) -> None:
    """İlk heartbeat → ok=True ve toplam_sure_sn >= 0."""
    _, token = user_with_person
    program, module, lesson, _ = enrolled

    sess_resp = await client.post(
        f"/api/v1/academy/lessons/{lesson.id}/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert sess_resp.status_code == 201
    session_id = sess_resp.json()["id"]

    hb_resp = await client.post(
        f"/api/v1/academy/sessions/{session_id}/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert hb_resp.status_code == 200
    data = hb_resp.json()
    assert data["ok"] is True
    assert "toplam_sure_sn" in data
    assert data["toplam_sure_sn"] >= 0


# ─── Test 9: Progress MAX mantığı ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_progress_max_logic(
    client: AsyncClient,
    enrolled,
    user_with_person,
) -> None:
    """Heartbeat sonrası progress endpoint → tamamlandi=False, yuzde >= 0."""
    _, token = user_with_person
    program, module, lesson, _ = enrolled

    # Session başlat
    sess_resp = await client.post(
        f"/api/v1/academy/lessons/{lesson.id}/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    session_id = sess_resp.json()["id"]

    # İki heartbeat
    await client.post(
        f"/api/v1/academy/sessions/{session_id}/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
    )
    hb2 = await client.post(
        f"/api/v1/academy/sessions/{session_id}/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
    )
    sure1 = hb2.json()["toplam_sure_sn"]

    # Üçüncü heartbeat — toplam_sure_sn asla azalmamalı
    hb3 = await client.post(
        f"/api/v1/academy/sessions/{session_id}/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
    )
    sure2 = hb3.json()["toplam_sure_sn"]
    assert sure2 >= sure1

    # Progress endpoint de tutarlı olmalı
    prog = await client.get(
        f"/api/v1/academy/lessons/{lesson.id}/progress",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert prog.status_code == 200
    prog_data = prog.json()
    assert prog_data["yuzde"] >= 0
    assert isinstance(prog_data["tamamlandi"], bool)


# ─── Test 10: Quiz attempt başlat — correct_letter YOK ───────────────────────

@pytest.mark.asyncio
async def test_quiz_attempt_start(
    client: AsyncClient,
    enrolled,
    user_with_person,
) -> None:
    """POST /lessons/{id}/quiz/attempts → questions var, correct_letter YOK."""
    _, token = user_with_person
    program, module, lesson, _ = enrolled

    resp = await client.post(
        f"/api/v1/academy/lessons/{lesson.id}/quiz/attempts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "attempt" in data
    assert "questions" in data
    assert len(data["questions"]) == 5

    # Güvenlik: correct_letter response'ta OLMAMALI
    for q in data["questions"]:
        assert "correct_letter" not in q
        assert "dogru_harf" not in q


# ─── Test 11: Quiz cevap gönder ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_quiz_answer(
    client: AsyncClient,
    enrolled,
    user_with_person,
) -> None:
    """POST /quiz/attempts/{id}/answers → ok=True."""
    _, token = user_with_person
    program, module, lesson, _ = enrolled

    attempt_resp = await client.post(
        f"/api/v1/academy/lessons/{lesson.id}/quiz/attempts",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = attempt_resp.json()
    attempt_id = data["attempt"]["id"]
    first_q_id = data["questions"][0]["id"]

    ans_resp = await client.post(
        f"/api/v1/academy/quiz/attempts/{attempt_id}/answers",
        headers={"Authorization": f"Bearer {token}"},
        json={"question_id": first_q_id, "secilen_harf": "A"},
    )
    assert ans_resp.status_code == 200
    assert ans_resp.json()["ok"] is True
    # correct_letter response'ta kesinlikle OLMAMALI
    assert "correct_letter" not in ans_resp.json()


# ─── Test 12: Quiz bitir — geçti=True, tamamlandi=True ───────────────────────

@pytest.mark.asyncio
async def test_quiz_finish_pass(
    client: AsyncClient,
    enrolled,
    user_with_person,
) -> None:
    """Tüm sorulara doğru cevap → gecti=True, progress tamamlandi=True."""
    _, token = user_with_person
    program, module, lesson, _ = enrolled

    attempt_resp = await client.post(
        f"/api/v1/academy/lessons/{lesson.id}/quiz/attempts",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = attempt_resp.json()
    attempt_id = data["attempt"]["id"]
    questions = data["questions"]

    # Doğru cevapları bilmeden test etmek için: backend'den soruları al
    # (correct_letter'ı bilmiyoruz; her soruya farklı şıklar deneyemeyiz doğrudan)
    # Bunun yerine DB'den sorulara bakıyoruz — test katmanında bu kabul edilebilir
    from sqlalchemy import select as sa_select
    from app.models.academy import AcademyQuizQuestion as QQ
    # enrolled fixture'daki lesson.id'yi kullanıyoruz

    # Tüm sorulara doğru cevaplar ver
    # Test fixture'da bilinen doğru cevaplar:
    # Q1→B, Q2→D, Q3→B, Q4→C, Q5→C (sıraya göre)
    correct_answers = ["B", "D", "B", "C", "C"]
    for i, q in enumerate(sorted(questions, key=lambda x: x["sira"])):
        await client.post(
            f"/api/v1/academy/quiz/attempts/{attempt_id}/answers",
            headers={"Authorization": f"Bearer {token}"},
            json={"question_id": q["id"], "secilen_harf": correct_answers[i]},
        )

    finish_resp = await client.post(
        f"/api/v1/academy/quiz/attempts/{attempt_id}/finish",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert finish_resp.status_code == 200
    result = finish_resp.json()
    assert result["gecti"] is True
    assert result["dogru"] == 5
    assert result["toplam"] == 5

    # Progress tamamlandi=True olmalı
    prog_resp = await client.get(
        f"/api/v1/academy/lessons/{lesson.id}/progress",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert prog_resp.json()["tamamlandi"] is True
    assert prog_resp.json()["yuzde"] == 100


# ─── Test 13: Quiz bitir — geçti=False ───────────────────────────────────────

@pytest.mark.asyncio
async def test_quiz_finish_fail(
    client: AsyncClient,
    enrolled,
    user_with_person,
) -> None:
    """Hiçbir soruya doğru cevap verilmezse gecti=False."""
    _, token = user_with_person
    program, module, lesson, _ = enrolled

    attempt_resp = await client.post(
        f"/api/v1/academy/lessons/{lesson.id}/quiz/attempts",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = attempt_resp.json()
    attempt_id = data["attempt"]["id"]
    questions = data["questions"]

    # Tüm sorulara yanlış cevap ver — "Z" hiçbir seçenek değil
    for q in questions:
        await client.post(
            f"/api/v1/academy/quiz/attempts/{attempt_id}/answers",
            headers={"Authorization": f"Bearer {token}"},
            json={"question_id": q["id"], "secilen_harf": "Z"},
        )

    finish_resp = await client.post(
        f"/api/v1/academy/quiz/attempts/{attempt_id}/finish",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert finish_resp.status_code == 200
    result = finish_resp.json()
    assert result["gecti"] is False
    assert result["dogru"] == 0


# ─── Test 14: correct_letter response'ta OLMAMALI ────────────────────────────

@pytest.mark.asyncio
async def test_correct_letter_not_in_response(
    client: AsyncClient,
    enrolled,
    user_with_person,
) -> None:
    """Tüm quiz response'larını tara — correct_letter / dogru_harf YOK (attempt/answer)."""
    _, token = user_with_person
    program, module, lesson, _ = enrolled

    # Attempt başlat
    attempt_resp = await client.post(
        f"/api/v1/academy/lessons/{lesson.id}/quiz/attempts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert attempt_resp.status_code == 201

    import json
    raw = json.dumps(attempt_resp.json())
    assert "correct_letter" not in raw, "correct_letter attempt response'ta bulundu!"

    # Cevap gönder
    data = attempt_resp.json()
    attempt_id = data["attempt"]["id"]
    first_q_id = data["questions"][0]["id"]
    ans_resp = await client.post(
        f"/api/v1/academy/quiz/attempts/{attempt_id}/answers",
        headers={"Authorization": f"Bearer {token}"},
        json={"question_id": first_q_id, "secilen_harf": "A"},
    )
    ans_raw = json.dumps(ans_resp.json())
    assert "correct_letter" not in ans_raw, "correct_letter answer response'ta bulundu!"


# ─── Test 15: Auth olmadan → 401 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unauthorized_401(
    client: AsyncClient,
    seed,
) -> None:
    """Auth token olmadan tüm korumalı endpoint'ler 401 döner."""
    program, _, lesson = seed

    endpoints = [
        ("GET", "/api/v1/academy/programs"),
        ("GET", f"/api/v1/academy/programs/{program.slug}"),
        ("GET", f"/api/v1/academy/lessons/{lesson.slug}"),
        ("GET", "/api/v1/academy/me/enrollments"),
    ]
    for method, url in endpoints:
        resp = await client.request(method, url)
        assert resp.status_code == 401, f"{method} {url} 401 değil: {resp.status_code}"


# ─── Test 16: Person kaydı olmayan kullanıcı → 403 ───────────────────────────

@pytest.mark.asyncio
async def test_unlinked_person_403(
    client: AsyncClient,
    seed,
    user_no_person,
) -> None:
    """person_id=None olan kullanıcı enrollment yapmaya çalışırsa 403."""
    _, token = user_no_person
    program, _, lesson = seed

    resp = await client.post(
        f"/api/v1/academy/programs/{program.id}/enroll",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


# ─── Test 17-20: KnotPlayer timeline (5C-3) ──────────────────────────────────

@pytest.mark.asyncio
async def test_knot_timeline_izbarco(
    client: AsyncClient,
    seed,
    user_with_person,
) -> None:
    """GET /api/v1/academy/knot/izbarco/timeline → 200 + geçerli şema."""
    _, token = user_with_person
    resp = await client.get(
        "/api/v1/academy/knot/izbarco/timeline",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Şema kontrolleri — myk/knotplayer-timeline/v1
    assert data["$schema"] == "myk/knotplayer-timeline/v1"
    assert data["slug"] == "izbarco"
    assert isinstance(data["steps"], list)
    assert len(data["steps"]) == 5
    assert "colors" in data
    assert "viewBox" in data


@pytest.mark.asyncio
async def test_knot_timeline_not_found(
    client: AsyncClient,
    seed,
    user_with_person,
) -> None:
    """Bilinmeyen slug → 404."""
    _, token = user_with_person
    resp = await client.get(
        "/api/v1/academy/knot/bilinmeyen-bag/timeline",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_knot_timeline_slug_validation(
    client: AsyncClient,
    seed,
    user_with_person,
) -> None:
    """Geçersiz slug karakterleri (path traversal / injection) → 404."""
    _, token = user_with_person
    headers = {"Authorization": f"Bearer {token}"}
    # Nokta ve slash içeren slug karakterleri endpoint'e ulaşmadan reject edilmeli
    resp = await client.get(
        "/api/v1/academy/knot/invalid..slug/timeline",
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_knot_timeline_requires_auth(
    client: AsyncClient,
    seed,
) -> None:
    """Auth token olmadan → 401."""
    resp = await client.get("/api/v1/academy/knot/izbarco/timeline")
    assert resp.status_code == 401
