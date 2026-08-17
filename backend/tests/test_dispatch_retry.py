"""dispatch retry ve e-posta şablonu testleri — Sprint 15A/15B.

15B ile birlikte retry mantığı event seviyesinden delivery seviyesine taşındı.
Tests 1, 5, 7: dispatch_pending_events (uçtan uca akış)
Tests 2-4, 6: dispatch_pending_deliveries (delivery-level retry)
Tests 8-10: E-posta şablonları (pure unit)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.models.club import Club
from app.models.events import DomainEvent
from app.models.notification_delivery import NotificationDelivery
from app.services.event_service import dispatch_pending_events
from app.services.notification_service import dispatch_pending_deliveries
from app.services.email_service import _build_event_email


# ─── Modül geneli SMTP guard bypass ──────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_smtp_configured(request):
    """Tüm testlerde smtp_host dolu göster; guard testin kendisi hariç."""
    if request.node.name == "test_dispatch_skips_when_smtp_not_configured":
        yield
        return
    mock_cfg = MagicMock()
    mock_cfg.smtp_host = "smtp.test.local"
    with patch("app.config.get_settings", return_value=mock_cfg):
        yield


# ─── Yardımcı fixture'lar ──────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def club_with_email(db_session, test_club: Club) -> Club:
    """Ayarlı e-posta adresine sahip test kulübü."""
    test_club.settings = {"email": "yonetici@testkulup.org"}
    await db_session.flush()
    return test_club


def _make_event(club_id: uuid.UUID, event_type: str = "payment.overdue") -> DomainEvent:
    """Test için minimal DomainEvent nesnesi."""
    return DomainEvent(
        id=uuid.uuid4(),
        club_id=club_id,
        event_type=event_type,
        aggregate_type="payment",
        aggregate_id=str(uuid.uuid4()),
        payload={"amount": "500", "due_date": "2026-08-01"},
        status="pending",
        attempt_count=0,
        last_error=None,
        next_attempt_at=None,
        created_at=datetime.now(tz=timezone.utc),
    )


def _make_delivery(
    club_id: uuid.UUID,
    event_id: uuid.UUID,
    email: str = "test@test.com",
    attempt_count: int = 0,
    next_attempt_at: datetime | None = None,
) -> NotificationDelivery:
    """Test için NotificationDelivery nesnesi."""
    return NotificationDelivery(
        id=uuid.uuid4(),
        club_id=club_id,
        event_id=event_id,
        recipient_email=email,
        channel="email",
        status="pending",
        attempt_count=attempt_count,
        next_attempt_at=next_attempt_at,
        created_at=datetime.now(tz=timezone.utc),
    )


# ─── 1. Başarılı uçtan uca gönderim ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_success(db_session, club_with_email: Club):
    """Başarılı gönderimde event status=done olmalı; sonuç dict doğru."""
    event = _make_event(club_with_email.id)
    db_session.add(event)
    await db_session.flush()

    with patch(
        "app.services.email_service.dispatch_domain_event_email",
        new_callable=AsyncMock,
    ) as mock_send:
        mock_send.return_value = None
        result = await dispatch_pending_events(db_session)

    assert result["sent"] == 1
    assert result["failed"] == 0
    assert result["retrying"] == 0

    await db_session.refresh(event)
    assert event.status == "done"
    assert event.processed_at is not None


# ─── 2. İlk gönderim başarısız → delivery retry planlanmalı ──────────────────

@pytest.mark.asyncio
async def test_delivery_first_failure_schedules_retry(db_session, club_with_email: Club):
    """İlk başarısızlıkta: delivery pending, attempt_count=1, next_attempt_at ≈ +5dk."""
    event = _make_event(club_with_email.id)
    db_session.add(event)
    await db_session.flush()

    # Delivery'yi önceden oluştur (dispatch_pending_deliveries direkt test için)
    delivery = _make_delivery(club_with_email.id, event.id, "yonetici@testkulup.org")
    db_session.add(delivery)
    await db_session.flush()

    with patch(
        "app.services.email_service.dispatch_domain_event_email",
        new_callable=AsyncMock,
        side_effect=Exception("SMTP connection refused"),
    ):
        result = await dispatch_pending_deliveries(db_session)

    assert result["sent"] == 0
    assert result["failed"] == 0
    assert result["retrying"] == 1

    await db_session.refresh(delivery)
    assert delivery.status == "pending"
    assert delivery.attempt_count == 1
    assert delivery.last_error == "SMTP connection refused"
    assert delivery.next_attempt_at is not None
    # +5dk ± 30sn tolerans; SQLite naive datetime döndürür
    next_at = delivery.next_attempt_at
    if next_at.tzinfo is not None:
        next_at = next_at.replace(tzinfo=None)
    expected_naive = datetime.utcnow() + timedelta(minutes=5)
    diff = abs((next_at - expected_naive).total_seconds())
    assert diff < 30, f"Beklenen ~+5dk, gerçek: {delivery.next_attempt_at}"


# ─── 3. İkinci gönderim başarısız → +25dk backoff ────────────────────────────

@pytest.mark.asyncio
async def test_delivery_second_failure_longer_backoff(db_session, club_with_email: Club):
    """attempt_count=1 olan delivery fail ederse: +25dk backoff."""
    event = _make_event(club_with_email.id)
    db_session.add(event)
    await db_session.flush()

    now = datetime.now(tz=timezone.utc)
    delivery = _make_delivery(
        club_with_email.id,
        event.id,
        "yonetici@testkulup.org",
        attempt_count=1,
        next_attempt_at=now - timedelta(minutes=1),  # süresi geçmiş → uygun
    )
    db_session.add(delivery)
    await db_session.flush()

    with patch(
        "app.services.email_service.dispatch_domain_event_email",
        new_callable=AsyncMock,
        side_effect=Exception("timeout"),
    ):
        result = await dispatch_pending_deliveries(db_session)

    assert result["retrying"] == 1

    await db_session.refresh(delivery)
    assert delivery.status == "pending"
    assert delivery.attempt_count == 2
    assert delivery.next_attempt_at is not None
    next_at = delivery.next_attempt_at
    if next_at.tzinfo is not None:
        next_at = next_at.replace(tzinfo=None)
    expected_naive = datetime.utcnow() + timedelta(minutes=25)
    diff = abs((next_at - expected_naive).total_seconds())
    assert diff < 30, f"Beklenen ~+25dk, gerçek: {delivery.next_attempt_at}"


# ─── 4. Üçüncü başarısızlık → kalıcı failed ──────────────────────────────────

@pytest.mark.asyncio
async def test_delivery_max_attempts_permanent_failure(db_session, club_with_email: Club):
    """attempt_count=2 olan delivery fail ederse status kalıcı 'failed' olmalı."""
    event = _make_event(club_with_email.id)
    db_session.add(event)
    await db_session.flush()

    now = datetime.now(tz=timezone.utc)
    delivery = _make_delivery(
        club_with_email.id,
        event.id,
        "yonetici@testkulup.org",
        attempt_count=2,
        next_attempt_at=now - timedelta(minutes=1),
    )
    db_session.add(delivery)
    await db_session.flush()

    with patch(
        "app.services.email_service.dispatch_domain_event_email",
        new_callable=AsyncMock,
        side_effect=Exception("permanent error"),
    ):
        result = await dispatch_pending_deliveries(db_session)

    assert result["failed"] == 1
    assert result["retrying"] == 0

    await db_session.refresh(delivery)
    assert delivery.status == "failed"
    assert delivery.attempt_count == 3
    assert delivery.last_error == "permanent error"


# ─── 5. Kulüp e-postası yok → event kalıcı failed, gönderim yapılmamalı ──────

@pytest.mark.asyncio
async def test_dispatch_no_club_email_permanent_failure(db_session, test_club: Club):
    """Kulüp e-postası tanımsızsa delivery oluşmamalı, event failed olmalı."""
    test_club.settings = {}  # e-posta yok
    await db_session.flush()

    event = _make_event(test_club.id)
    db_session.add(event)
    await db_session.flush()

    with patch(
        "app.services.email_service.dispatch_domain_event_email",
        new_callable=AsyncMock,
    ) as mock_send:
        result = await dispatch_pending_events(db_session)
        mock_send.assert_not_called()

    assert result["sent"] == 0

    await db_session.refresh(event)
    assert event.status == "failed"
    assert event.attempt_count == 0  # delivery atlaması; deneme sayılmamalı


# ─── 6. Henüz zamanı gelmeyen delivery atlanmalı ─────────────────────────────

@pytest.mark.asyncio
async def test_delivery_skips_future_retry(db_session, club_with_email: Club):
    """next_attempt_at ilerideyse delivery bu çalışmada işlenmemeli."""
    event = _make_event(club_with_email.id)
    db_session.add(event)
    await db_session.flush()

    future = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    delivery = _make_delivery(
        club_with_email.id,
        event.id,
        "yonetici@testkulup.org",
        attempt_count=1,
        next_attempt_at=future,
    )
    db_session.add(delivery)
    await db_session.flush()

    with patch(
        "app.services.email_service.dispatch_domain_event_email",
        new_callable=AsyncMock,
    ) as mock_send:
        result = await dispatch_pending_deliveries(db_session)
        mock_send.assert_not_called()

    assert result["sent"] == 0
    assert result["failed"] == 0
    assert result["retrying"] == 0


# ─── 7. SMTP yapılandırılmamışsa dispatch erken çıkmalı ──────────────────────

@pytest.mark.asyncio
async def test_dispatch_skips_when_smtp_not_configured(db_session, club_with_email: Club):
    """SMTP_HOST boşsa eventler 'done' işaretlenmemeli; 'pending' kalmalı."""
    from unittest.mock import patch as _patch

    event = _make_event(club_with_email.id)
    db_session.add(event)
    await db_session.flush()

    with _patch("app.config.get_settings") as mock_settings:
        mock_settings.return_value.smtp_host = ""
        result = await dispatch_pending_events(db_session)

    assert result == {"sent": 0, "failed": 0, "retrying": 0}

    await db_session.refresh(event)
    assert event.status == "pending"
    assert event.attempt_count == 0


# ─── 8. Şablon: payment.created ──────────────────────────────────────────────

def test_email_template_payment_created():
    """payment.created şablonu doğru konu ve tutar içermeli."""
    event = DomainEvent(
        id=uuid.uuid4(),
        club_id=uuid.uuid4(),
        event_type="payment.created",
        aggregate_type="payment",
        payload={
            "amount": "1500",
            "payment_type": "Üyelik",
            "payment_method": "Nakit",
            "status": "paid",
        },
        status="pending",
        attempt_count=0,
    )
    subject, html = _build_event_email(event)
    assert "💳" in subject
    assert "Ödeme" in subject
    assert "1500" in html
    assert "Ödendi" in html
    assert "Üyelik" in html


# ─── 9. Şablon: training.session.created ─────────────────────────────────────

def test_email_template_training_session_created():
    """training.session.created şablonu kurs adı ve tarihi içermeli."""
    event = DomainEvent(
        id=uuid.uuid4(),
        club_id=uuid.uuid4(),
        event_type="training.session.created",
        aggregate_type="training_session",
        payload={
            "course_name": "Optimist Temel Eğitim",
            "session_date": "2026-08-20",
            "start_time": "14:00",
            "end_time": "16:00",
            "instructor_name": "Ahmet Yılmaz",
        },
        status="pending",
        attempt_count=0,
    )
    subject, html = _build_event_email(event)
    assert "🗓️" in subject
    assert "Optimist Temel Eğitim" in subject
    assert "2026-08-20" in html
    assert "14:00" in html
    assert "Ahmet Yılmaz" in html


# ─── 10. Bilinmeyen event tipi → genel şablon ────────────────────────────────

def test_email_template_unknown_event_type():
    """Bilinmeyen event tipi genel şablon döndürmeli, hata fırlatmamalı."""
    event = DomainEvent(
        id=uuid.uuid4(),
        club_id=uuid.uuid4(),
        event_type="custom.unknown.event",
        aggregate_type="unknown",
        payload={},
        status="pending",
        attempt_count=0,
    )
    subject, html = _build_event_email(event)
    assert "custom.unknown.event" in subject
    assert "Platform Bildirimi" in html
