"""notification_deliveries sistemi testleri — Sprint 15B.

Test kapsamı:
  1. Başarılı tekli gönderim: delivery done, event done
  2. Çoklu veli: iki veliye ayrı delivery, her ikisi gönderilince event done
  3. Guardian opt-out: can_receive_notifications=False olan veli dışlanmalı
  4. Tüm veliler opt-out: kulüp adminine fallback
     — Politika: veli e-postası bulunamazsa "operasyonel uyarı" olarak
       kulüp yönetim adresi kullanılır; süresi yaklaşan belge bildirimi
       veliye ulaşmaz, yönetici takip etmeli.
  5. Kısmi başarı: bir veliye gönderim başarılı, diğerine başarısız → event pending kalmalı
  6. Alıcı bulunamazsa: delivery oluşmaz, dispatcher event'i failed yapar
  7. Tenant izolasyonu: farklı kulüp event'i görünmemeli
  8. Idempotent dispatch: aynı event tekrar çalıştırılırsa delivery tekrarlanmaz
  9. Ödeme sahibi e-posta çözümleme: Person.email kullanılmalı
  10. payment.overdue — Person.email yoksa User.email fallback
  11. training.session.starts_tomorrow: kayıtlı sporcu velisine gönderim (uçtan uca)
  12. training.session.starts_tomorrow: kayıt yoksa kulüp adminine fallback
  13. equipment.maintenance.due: kulüp yönetim e-postasına gönderim
  14. payment.created: kulüp yönetim e-postasına gönderim
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.models.club import Club
from app.models.events import DomainEvent
from app.models.notification_delivery import NotificationDelivery
from app.models.person import Person
from app.models.person_guardian import PersonGuardian
from app.models.user import User
from app.core.security import hash_password
from app.services.notification_service import (
    create_deliveries_for_event,
    dispatch_pending_deliveries,
    resolve_recipients,
)


# ─── SMTP guard bypass (tüm dispatch testleri için) ───────────────────────────

@pytest.fixture(autouse=True)
def mock_smtp_configured(request):
    if request.node.name == "test_dispatch_skips_when_smtp_not_configured":
        yield
        return
    mock_cfg = MagicMock()
    mock_cfg.smtp_host = "smtp.test.local"
    with patch("app.config.get_settings", return_value=mock_cfg):
        yield


# ─── Yardımcı builder'lar ─────────────────────────────────────────────────────

def _make_event(
    club_id: uuid.UUID,
    event_type: str = "payment.created",
    payload: dict | None = None,
) -> DomainEvent:
    return DomainEvent(
        id=uuid.uuid4(),
        club_id=club_id,
        event_type=event_type,
        aggregate_type="test",
        aggregate_id=str(uuid.uuid4()),
        payload=payload or {},
        status="pending",
        attempt_count=0,
        created_at=datetime.now(tz=timezone.utc),
    )


async def _make_person(
    db, club_id: uuid.UUID, email: str | None = None
) -> Person:
    p = Person(
        id=uuid.uuid4(),
        club_id=club_id,
        first_name="Test",
        last_name="Kişi",
        email=email,
        is_active=True,
        is_deleted=False,
    )
    db.add(p)
    await db.flush()
    return p


async def _make_user(
    db, club_id: uuid.UUID, person_id: uuid.UUID, email: str
) -> User:
    u = User(
        id=uuid.uuid4(),
        club_id=club_id,
        person_id=person_id,
        email=email,
        password_hash=hash_password("Test1234!"),
        full_name="Test Kullanıcı",
        role="uye",
        is_active=True,
        is_deleted=False,
    )
    db.add(u)
    await db.flush()
    return u


async def _make_guardian_link(
    db,
    club_id: uuid.UUID,
    athlete_id: uuid.UUID,
    guardian_id: uuid.UUID,
    can_receive: bool = True,
) -> PersonGuardian:
    link = PersonGuardian(
        id=uuid.uuid4(),
        club_id=club_id,
        athlete_person_id=athlete_id,
        guardian_person_id=guardian_id,
        relationship_type="veli",
        can_receive_notifications=can_receive,
        is_primary=True,
    )
    db.add(link)
    await db.flush()
    return link


# ─── 1. Başarılı tekli gönderim ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_single_delivery_success(db_session, test_club: Club):
    """Başarılı gönderimde delivery done, event done olmalı."""
    test_club.settings = {"email": "admin@kulup.org"}
    await db_session.flush()

    event = _make_event(test_club.id)
    db_session.add(event)
    await db_session.flush()

    n = await create_deliveries_for_event(event, db_session)
    assert n == 1

    with patch(
        "app.services.email_service.dispatch_domain_event_email",
        new_callable=AsyncMock,
    ):
        result = await dispatch_pending_deliveries(db_session)

    assert result["sent"] == 1
    assert result["failed"] == 0

    await db_session.refresh(event)
    assert event.status == "done"


# ─── 2. Çoklu veli ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_multiple_guardians_separate_deliveries(db_session, test_club: Club):
    """İki veliye ayrı delivery oluşturulmalı; her ikisi gönderilince event done."""
    test_club.settings = {"email": "admin@kulup.org"}
    await db_session.flush()

    athlete = await _make_person(db_session, test_club.id)
    guardian1 = await _make_person(db_session, test_club.id, email="veli1@test.com")
    guardian2 = await _make_person(db_session, test_club.id, email="veli2@test.com")

    await _make_guardian_link(db_session, test_club.id, athlete.id, guardian1.id)
    await _make_guardian_link(db_session, test_club.id, athlete.id, guardian2.id)

    event = _make_event(
        test_club.id,
        event_type="athlete.license.expiring_soon",
        payload={"person_id": str(athlete.id), "expiry_date": "2026-09-01", "days_remaining": 15},
    )
    db_session.add(event)
    await db_session.flush()

    n = await create_deliveries_for_event(event, db_session)
    assert n == 2  # iki veli = iki delivery

    with patch(
        "app.services.email_service.dispatch_domain_event_email",
        new_callable=AsyncMock,
    ):
        result = await dispatch_pending_deliveries(db_session)

    assert result["sent"] == 2
    await db_session.refresh(event)
    assert event.status == "done"


# ─── 3. Guardian opt-out ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_guardian_opt_out_excluded(db_session, test_club: Club):
    """can_receive_notifications=False olan veli dışlanmalı."""
    test_club.settings = {"email": "admin@kulup.org"}
    await db_session.flush()

    athlete = await _make_person(db_session, test_club.id)
    guardian_opted_out = await _make_person(db_session, test_club.id, email="optout@test.com")
    guardian_opted_in = await _make_person(db_session, test_club.id, email="optin@test.com")

    await _make_guardian_link(db_session, test_club.id, athlete.id, guardian_opted_out.id, can_receive=False)
    await _make_guardian_link(db_session, test_club.id, athlete.id, guardian_opted_in.id, can_receive=True)

    event = _make_event(
        test_club.id,
        event_type="athlete.license.expiring_soon",
        payload={"person_id": str(athlete.id), "expiry_date": "2026-09-01", "days_remaining": 15},
    )
    db_session.add(event)
    await db_session.flush()

    n = await create_deliveries_for_event(event, db_session)
    assert n == 1  # yalnızca opt-in veli

    # Delivery'nin opt-out veliye ait olmadığını doğrula
    from sqlalchemy import select as sa_select
    deliveries = (await db_session.execute(
        sa_select(NotificationDelivery).where(NotificationDelivery.event_id == event.id)
    )).scalars().all()
    emails = {d.recipient_email for d in deliveries}
    assert "optout@test.com" not in emails
    assert "optin@test.com" in emails


# ─── 4. Tüm veliler opt-out → kulüp adminine fallback ────────────────────────

@pytest.mark.asyncio
async def test_all_guardians_opted_out_fallback_to_admin(db_session, test_club: Club):
    """Tüm veliler opt-out ise kulüp admin e-postasına fallback."""
    test_club.settings = {"email": "admin@kulup.org"}
    await db_session.flush()

    athlete = await _make_person(db_session, test_club.id)
    guardian = await _make_person(db_session, test_club.id, email="optout@test.com")
    await _make_guardian_link(db_session, test_club.id, athlete.id, guardian.id, can_receive=False)

    event = _make_event(
        test_club.id,
        event_type="athlete.health_report.expiring_soon",
        payload={"person_id": str(athlete.id)},
    )
    db_session.add(event)
    await db_session.flush()

    n = await create_deliveries_for_event(event, db_session)
    assert n == 1

    from sqlalchemy import select as sa_select
    deliveries = (await db_session.execute(
        sa_select(NotificationDelivery).where(NotificationDelivery.event_id == event.id)
    )).scalars().all()
    assert deliveries[0].recipient_email == "admin@kulup.org"
    assert deliveries[0].recipient_person_id is None  # kulüp admini, kişi değil


# ─── 5. Kısmi başarı ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_partial_success_event_stays_pending(db_session, test_club: Club):
    """Bir veliye gönderim başarılı, diğerine başarısız → event pending kalmalı."""
    test_club.settings = {"email": "admin@kulup.org"}
    await db_session.flush()

    athlete = await _make_person(db_session, test_club.id)
    g1 = await _make_person(db_session, test_club.id, email="veli1@test.com")
    g2 = await _make_person(db_session, test_club.id, email="veli2@test.com")
    await _make_guardian_link(db_session, test_club.id, athlete.id, g1.id)
    await _make_guardian_link(db_session, test_club.id, athlete.id, g2.id)

    event = _make_event(
        test_club.id,
        event_type="athlete.visa.expiring_soon",
        payload={"person_id": str(athlete.id)},
    )
    db_session.add(event)
    await db_session.flush()

    await create_deliveries_for_event(event, db_session)

    call_count = 0
    async def mock_send_partial(event, to_email):
        nonlocal call_count
        call_count += 1
        if call_count == 2:  # ikinci alıcıda hata
            raise Exception("SMTP timeout")

    with patch(
        "app.services.email_service.dispatch_domain_event_email",
        side_effect=mock_send_partial,
    ):
        result = await dispatch_pending_deliveries(db_session)

    assert result["sent"] == 1
    assert result["retrying"] == 1  # retry bekliyor

    # Event henüz tamamlanmamalı — bir delivery hâlâ pending
    await db_session.refresh(event)
    assert event.status == "pending"


# ─── 6. Alıcı bulunamazsa event failed ───────────────────────────────────────

@pytest.mark.asyncio
async def test_no_recipient_marks_event_failed(db_session, test_club: Club):
    """Alıcı çözümlenemezse event failed olmalı, delivery oluşmamalı."""
    test_club.settings = {}  # e-posta yok
    await db_session.flush()

    event = _make_event(test_club.id, event_type="payment.created")
    db_session.add(event)
    await db_session.flush()

    n = await create_deliveries_for_event(event, db_session)
    assert n == 0  # delivery oluşmadı


# ─── 7. Tenant izolasyonu ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tenant_isolation(db_session, test_club: Club):
    """Farklı kulübün event'i dispatch'e dahil edilmemeli."""
    # İkinci kulüp oluştur
    other_club = Club(
        id=uuid.uuid4(),
        slug=f"other-{uuid.uuid4().hex[:6]}",
        name="Diğer Kulüp",
        plan="starter",
        is_active=True,
        settings={"email": "other@kulup.org"},
    )
    db_session.add(other_club)
    test_club.settings = {"email": "main@kulup.org"}
    await db_session.flush()

    # Kendi kulübümüzün event'i
    own_event = _make_event(test_club.id)
    # Diğer kulübün event'i
    other_event = _make_event(other_club.id)
    db_session.add(own_event)
    db_session.add(other_event)
    await db_session.flush()

    await create_deliveries_for_event(own_event, db_session)
    await create_deliveries_for_event(other_event, db_session)

    with patch(
        "app.services.email_service.dispatch_domain_event_email",
        new_callable=AsyncMock,
    ):
        result = await dispatch_pending_deliveries(db_session)

    # Her iki kulübün delivery'si de gönderilmeli (izolasyon dispatch'i engellemez)
    assert result["sent"] == 2

    # Delivery'lerin club_id'leri doğru tenant'a ait olmalı
    from sqlalchemy import select as sa_select
    own_deliveries = (await db_session.execute(
        sa_select(NotificationDelivery).where(NotificationDelivery.club_id == test_club.id)
    )).scalars().all()
    other_deliveries = (await db_session.execute(
        sa_select(NotificationDelivery).where(NotificationDelivery.club_id == other_club.id)
    )).scalars().all()
    assert len(own_deliveries) == 1
    assert len(other_deliveries) == 1
    assert own_deliveries[0].recipient_email == "main@kulup.org"
    assert other_deliveries[0].recipient_email == "other@kulup.org"


# ─── 8. Idempotent dispatch ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_idempotent_delivery_creation(db_session, test_club: Club):
    """Aynı event için iki kez create_deliveries_for_event çağrılınca duplicate oluşmamalı."""
    test_club.settings = {"email": "admin@kulup.org"}
    await db_session.flush()

    event = _make_event(test_club.id)
    db_session.add(event)
    await db_session.flush()

    n1 = await create_deliveries_for_event(event, db_session)
    n2 = await create_deliveries_for_event(event, db_session)  # ikinci çağrı

    assert n1 == 1
    assert n2 == 0  # zaten var, yeni oluşturulmadı

    from sqlalchemy import select as sa_select, func as sa_func
    count = (await db_session.execute(
        sa_select(sa_func.count(NotificationDelivery.id)).where(
            NotificationDelivery.event_id == event.id
        )
    )).scalar_one()
    assert count == 1


# ─── 9. Ödeme sahibi — Person.email ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_payment_overdue_resolves_person_email(db_session, test_club: Club):
    """payment.overdue payload'undaki person_id → Person.email çözülmeli."""
    test_club.settings = {"email": "admin@kulup.org"}
    await db_session.flush()

    person = await _make_person(db_session, test_club.id, email="borclu@test.com")

    event = _make_event(
        test_club.id,
        event_type="payment.overdue",
        payload={"person_id": str(person.id), "amount": "500", "due_date": "2026-08-01"},
    )
    db_session.add(event)
    await db_session.flush()

    recipients = await resolve_recipients(event, db_session)
    assert len(recipients) == 1
    assert recipients[0].email == "borclu@test.com"
    assert recipients[0].person_id == person.id


# ─── 10. payment.overdue — User.email fallback ───────────────────────────────

@pytest.mark.asyncio
async def test_payment_overdue_falls_back_to_user_email(db_session, test_club: Club):
    """Person.email yoksa User.email fallback kullanılmalı."""
    test_club.settings = {"email": "admin@kulup.org"}
    await db_session.flush()

    # Person.email None
    person = await _make_person(db_session, test_club.id, email=None)
    # Person'a bağlı User
    await _make_user(db_session, test_club.id, person.id, email="user@test.com")

    event = _make_event(
        test_club.id,
        event_type="payment.overdue",
        payload={"person_id": str(person.id), "amount": "750"},
    )
    db_session.add(event)
    await db_session.flush()

    recipients = await resolve_recipients(event, db_session)
    assert len(recipients) == 1
    assert recipients[0].email == "user@test.com"


# ─── 11. training.session.starts_tomorrow — sporcu velisine gönderim ─────────

@pytest.mark.asyncio
async def test_training_session_tomorrow_resolves_guardian(db_session, test_club: Club):
    """Kursa kayıtlı sporcunun velisine gönderim uçtan uca çalışmalı."""
    from app.models.training import TrainingCourse, TrainingEnrollment

    test_club.settings = {"email": "admin@kulup.org"}
    await db_session.flush()

    # Kurs oluştur
    course = TrainingCourse(
        id=uuid.uuid4(),
        club_id=test_club.id,
        name="Optimist Temel",
        status="aktif",
        is_deleted=False,
    )
    db_session.add(course)

    # Sporcu ve velisi
    athlete = await _make_person(db_session, test_club.id)
    guardian = await _make_person(db_session, test_club.id, email="veli@test.com")
    await _make_guardian_link(db_session, test_club.id, athlete.id, guardian.id)

    # Kayıt
    enrollment = TrainingEnrollment(
        id=uuid.uuid4(),
        club_id=test_club.id,
        course_id=course.id,
        person_id=athlete.id,
        status="active",
        payment_status="paid",
        is_deleted=False,
    )
    db_session.add(enrollment)
    await db_session.flush()

    event = _make_event(
        test_club.id,
        event_type="training.session.starts_tomorrow",
        payload={"course_id": str(course.id), "course_name": "Optimist Temel", "session_date": "2026-08-18"},
    )
    db_session.add(event)
    await db_session.flush()

    # Resolve + delivery oluştur
    n = await create_deliveries_for_event(event, db_session)
    assert n == 1

    from sqlalchemy import select as sa_select
    deliveries = (await db_session.execute(
        sa_select(NotificationDelivery).where(NotificationDelivery.event_id == event.id)
    )).scalars().all()
    assert deliveries[0].recipient_email == "veli@test.com"

    # Uçtan uca gönderim
    with patch(
        "app.services.email_service.dispatch_domain_event_email",
        new_callable=AsyncMock,
    ):
        result = await dispatch_pending_deliveries(db_session)

    assert result["sent"] == 1
    await db_session.refresh(event)
    assert event.status == "done"


# ─── 12. training.session.starts_tomorrow — kayıt yok → admin fallback ───────

@pytest.mark.asyncio
async def test_training_session_tomorrow_no_enrollment_falls_back_to_admin(
    db_session, test_club: Club
):
    """Kursa kayıtlı sporcu yoksa kulüp adminine fallback yapılmalı."""
    from app.models.training import TrainingCourse

    test_club.settings = {"email": "admin@kulup.org"}
    await db_session.flush()

    course = TrainingCourse(
        id=uuid.uuid4(),
        club_id=test_club.id,
        name="Boş Kurs",
        status="aktif",
        is_deleted=False,
    )
    db_session.add(course)
    await db_session.flush()

    event = _make_event(
        test_club.id,
        event_type="training.session.starts_tomorrow",
        payload={"course_id": str(course.id), "session_date": "2026-08-18"},
    )
    db_session.add(event)
    await db_session.flush()

    recipients = await resolve_recipients(event, db_session)
    assert len(recipients) == 1
    assert recipients[0].email == "admin@kulup.org"
    assert recipients[0].person_id is None  # kulüp admini, kişi değil


# ─── 13. equipment.maintenance.due — kulüp yönetim e-postası ─────────────────

@pytest.mark.asyncio
async def test_equipment_maintenance_resolves_admin_email(db_session, test_club: Club):
    """Ekipman bildirimleri kulüp yönetim e-postasına gönderilmeli."""
    test_club.settings = {"email": "admin@kulup.org"}
    await db_session.flush()

    event = _make_event(
        test_club.id,
        event_type="equipment.maintenance.due",
        payload={"name": "Optimist #7", "next_maintenance_date": "2026-09-01", "days_remaining": 14},
    )
    db_session.add(event)
    await db_session.flush()

    recipients = await resolve_recipients(event, db_session)
    assert len(recipients) == 1
    assert recipients[0].email == "admin@kulup.org"
    assert recipients[0].person_id is None


# ─── 14. payment.created — kulüp yönetim e-postası ──────────────────────────

@pytest.mark.asyncio
async def test_payment_created_resolves_admin_email(db_session, test_club: Club):
    """payment.created bildirimi kulüp yönetim e-postasına gönderilmeli."""
    test_club.settings = {"email": "admin@kulup.org"}
    await db_session.flush()

    event = _make_event(
        test_club.id,
        event_type="payment.created",
        payload={"amount": "1500", "payment_type": "Üyelik", "status": "paid"},
    )
    db_session.add(event)
    await db_session.flush()

    recipients = await resolve_recipients(event, db_session)
    assert len(recipients) == 1
    assert recipients[0].email == "admin@kulup.org"


# ─── 15. Concurrent claiming: aynı delivery iki kez gönderilmemeli ───────────

@pytest.mark.asyncio
async def test_concurrent_dispatch_does_not_double_send(
    db_session, test_club: Club, session_factory
):
    """İki eş zamanlı dispatch (asyncio.gather + ayrı session) aynı delivery'yi
    yalnızca bir kez göndermelidir.

    asyncio.Lock (SQLite) ve FOR UPDATE SKIP LOCKED (PostgreSQL) mekanizmalarının
    her iki durumda da double-send'i engellediğini doğrular.
    """
    test_club.settings = {"email": "admin@kulup.org"}
    await db_session.flush()

    event = _make_event(test_club.id)
    db_session.add(event)
    await db_session.flush()

    await create_deliveries_for_event(event, db_session)
    await db_session.commit()  # delivery kalıcı; diğer session'lar görebilir

    send_count = 0

    async def counting_send(_event, _to_email):
        nonlocal send_count
        send_count += 1

    async def run_worker():
        """Her worker kendi DB session'ıyla dispatch çalıştırır."""
        async with session_factory() as session:
            with patch(
                "app.services.email_service.dispatch_domain_event_email",
                side_effect=counting_send,
            ):
                return await dispatch_pending_deliveries(session)

    # İki worker eş zamanlı başlatılır — sadece biri delivery'yi claim edip göndermelidir
    r1, r2 = await asyncio.gather(run_worker(), run_worker())

    assert send_count == 1, f"Beklenen 1 gönderim, gerçek: {send_count}"
    assert r1["sent"] + r2["sent"] == 1
    assert r1["retrying"] + r2["retrying"] == 0
    assert r1["failed"] + r2["failed"] == 0


# ─── 16. Crash recovery: takılı claim serbest bırakılmalı ────────────────────

@pytest.mark.asyncio
async def test_stuck_claim_is_released(db_session, test_club: Club):
    """processing_since + CLAIM_TIMEOUT_MINUTES geçmiş → bir sonraki dispatch serbest bırakır."""
    from datetime import timedelta
    from app.services.notification_service import CLAIM_TIMEOUT_MINUTES

    test_club.settings = {"email": "admin@kulup.org"}
    await db_session.flush()

    event = _make_event(test_club.id)
    db_session.add(event)
    await db_session.flush()

    delivery = NotificationDelivery(
        id=uuid.uuid4(),
        club_id=test_club.id,
        event_id=event.id,
        recipient_email="admin@kulup.org",
        channel="email",
        status="pending",
        attempt_count=0,
        claimed_worker_id="dead-worker-xyz",
        processing_since=datetime.utcnow() - timedelta(minutes=CLAIM_TIMEOUT_MINUTES + 1),
    )
    db_session.add(delivery)
    await db_session.flush()

    with patch(
        "app.services.email_service.dispatch_domain_event_email",
        new_callable=AsyncMock,
    ):
        result = await dispatch_pending_deliveries(db_session)

    assert result["sent"] == 1

    await db_session.refresh(delivery)
    assert delivery.status == "done"
    assert delivery.claimed_worker_id is None
