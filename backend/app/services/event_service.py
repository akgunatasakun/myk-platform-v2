"""Event Service — domain event yayımlama ve nightly scan fonksiyonları.

İki sorumluluk:
  1. emit_event()     — request handler içinden çağrılır, aynı DB transaction'a
                        outbox pattern ile event yazar (commit yok).
  2. scan_*()         — APScheduler nightly job'dan çağrılır, kendi DB oturumunu
                        açar, yinelenen event'leri PostgreSQL ON CONFLICT ile atlar.

Tasarım kararları:
  - emit_event() hiçbir zaman commit etmez; çağıran router zaten commit eder.
  - scan_*() fonksiyonları bağımsız AsyncSession kullanır (scheduler context'i
    bir HTTP request değil).
  - Duplicate önleme: migration 0012'deki partial unique index
    (club_id, event_type, aggregate_id, date(scheduled_for AT TIME ZONE 'UTC'))
    üzerinden PostgreSQL'de conflict-on-nothing (INSERT … ON CONFLICT DO NOTHING).
    SQLite test ortamında index yoktur; INSERT hata vermez, upsert gerekmez.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.events import DomainEvent

logger = logging.getLogger(__name__)

# ── Nightly scan eşikleri ─────────────────────────────────────────────────────
PAYMENT_OVERDUE_CHECK_DAYS = 0        # due_date < today
MAINTENANCE_WARNING_DAYS   = 14
INSURANCE_WARNING_DAYS     = 30
ATHLETE_DOC_WARNING_DAYS   = 30
SESSION_TOMORROW_HOURS     = 24       # session_date == yarın


# ─────────────────────────────────────────────────────────────────────────────
# 1. emit_event() — anlık (outbox pattern)
# ─────────────────────────────────────────────────────────────────────────────

async def emit_event(
    db: AsyncSession,
    club_id: uuid.UUID,
    event_type: str,
    aggregate_type: str,
    aggregate_id: Optional[Any] = None,
    payload: Optional[dict] = None,
    scheduled_for: Optional[datetime] = None,
) -> None:
    """Aynı DB oturumuna (outbox) bir domain event yazar.

    Commit yapmaz — çağıran endpoint zaten commit eder.
    Hata durumunda loglayıp sessizce geçer; main işlem etkilenmez.
    """
    try:
        event = DomainEvent(
            club_id=club_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id) if aggregate_id is not None else None,
            payload=payload or {},
            status="pending",
            scheduled_for=scheduled_for or datetime.now(tz=timezone.utc),
        )
        db.add(event)
    except Exception:
        logger.exception(
            "emit_event() başarısız: event_type=%s aggregate=%s/%s",
            event_type, aggregate_type, aggregate_id,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Nightly scan yardımcıları
# ─────────────────────────────────────────────────────────────────────────────

def _day_start(d: date) -> datetime:
    """Verilen tarih için UTC gün başlangıcı."""
    return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)


async def _insert_event_if_new(
    db: AsyncSession,
    club_id: uuid.UUID,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict,
    scheduled_for: datetime,
) -> bool:
    """Duplicate partial index varsa INSERT atlanır (ON CONFLICT DO NOTHING).
    Eklendiyse True, atlandıysa False döner."""
    # SQLite test ortamı için önce var mı kontrol et
    bind = await db.connection()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        stmt = text("""
            INSERT INTO domain_events
              (id, club_id, event_type, aggregate_type, aggregate_id,
               payload, status, scheduled_for, created_at)
            VALUES
              (:id, :club_id, :event_type, :aggregate_type, :aggregate_id,
               CAST(:payload AS jsonb), 'pending', :scheduled_for, now())
            ON CONFLICT DO NOTHING
        """)
        import json
        result = await db.execute(stmt, {
            "id": str(uuid.uuid4()),
            "club_id": str(club_id),
            "event_type": event_type,
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "payload": json.dumps(payload),
            "scheduled_for": scheduled_for,
        })
        return result.rowcount > 0
    else:
        # SQLite: basit varlık kontrolü
        existing = await db.execute(
            select(DomainEvent).where(
                DomainEvent.club_id == club_id,
                DomainEvent.event_type == event_type,
                DomainEvent.aggregate_id == aggregate_id,
                func.date(DomainEvent.scheduled_for) == scheduled_for.date(),
            )
        )
        if existing.scalar_one_or_none() is not None:
            return False
        ev = DomainEvent(
            club_id=club_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            status="pending",
            scheduled_for=scheduled_for,
        )
        db.add(ev)
        return True


# ── Scan fonksiyonları ────────────────────────────────────────────────────────

async def scan_overdue_payments(db: AsyncSession) -> int:
    """status=pending ve due_date < today olan ödemelere event üret."""
    from app.models.payment import Payment

    today = date.today()
    sf = _day_start(today)

    result = await db.execute(
        select(Payment).where(
            Payment.status == "pending",
            Payment.due_date < today,
            Payment.is_deleted.is_(False),
        )
    )
    payments = result.scalars().all()

    count = 0
    for p in payments:
        added = await _insert_event_if_new(
            db,
            club_id=p.club_id,
            event_type="payment.overdue",
            aggregate_type="payment",
            aggregate_id=str(p.id),
            payload={
                "amount": str(p.amount),
                "due_date": str(p.due_date),
                "person_id": str(p.person_id) if p.person_id else None,
                "payment_type": p.payment_type,
            },
            scheduled_for=sf,
        )
        if added:
            count += 1

    logger.info("scan_overdue_payments: %d yeni event", count)
    return count


async def scan_maintenance_due(db: AsyncSession) -> int:
    """next_maintenance_date ≤ today+14 olan ekipmanlar."""
    from app.models.equipment import Equipment

    today = date.today()
    cutoff = today + timedelta(days=MAINTENANCE_WARNING_DAYS)
    sf = _day_start(today)

    result = await db.execute(
        select(Equipment).where(
            Equipment.next_maintenance_date <= cutoff,
            Equipment.next_maintenance_date.isnot(None),
            Equipment.is_deleted.is_(False),
        )
    )
    items = result.scalars().all()

    count = 0
    for eq in items:
        days_left = (eq.next_maintenance_date - today).days
        added = await _insert_event_if_new(
            db,
            club_id=eq.club_id,
            event_type="equipment.maintenance.due",
            aggregate_type="equipment",
            aggregate_id=str(eq.id),
            payload={
                "name": eq.name,
                "next_maintenance_date": str(eq.next_maintenance_date),
                "days_remaining": days_left,
                "status": eq.status,
            },
            scheduled_for=sf,
        )
        if added:
            count += 1

    logger.info("scan_maintenance_due: %d yeni event", count)
    return count


async def scan_insurance_expiring(db: AsyncSession) -> int:
    """insurance_expiry_date ≤ today+30 olan ekipmanlar."""
    from app.models.equipment import Equipment

    today = date.today()
    cutoff = today + timedelta(days=INSURANCE_WARNING_DAYS)
    sf = _day_start(today)

    result = await db.execute(
        select(Equipment).where(
            Equipment.insurance_expiry_date <= cutoff,
            Equipment.insurance_expiry_date.isnot(None),
            Equipment.is_deleted.is_(False),
        )
    )
    items = result.scalars().all()

    count = 0
    for eq in items:
        days_left = (eq.insurance_expiry_date - today).days
        added = await _insert_event_if_new(
            db,
            club_id=eq.club_id,
            event_type="equipment.insurance.expiring_soon",
            aggregate_type="equipment",
            aggregate_id=str(eq.id),
            payload={
                "name": eq.name,
                "insurance_expiry_date": str(eq.insurance_expiry_date),
                "days_remaining": days_left,
            },
            scheduled_for=sf,
        )
        if added:
            count += 1

    logger.info("scan_insurance_expiring: %d yeni event", count)
    return count


async def scan_athlete_docs(db: AsyncSession) -> int:
    """Lisans / vize / sağlık raporu dolmuş veya 30 gün içinde dolacak sporcular."""
    from app.models.athlete_profile import AthleteProfile

    today = date.today()
    cutoff = today + timedelta(days=ATHLETE_DOC_WARNING_DAYS)
    sf = _day_start(today)

    result = await db.execute(
        select(AthleteProfile).where(
            AthleteProfile.license_expiry_date.isnot(None)
            | AthleteProfile.visa_expiry_date.isnot(None)
            | AthleteProfile.health_report_expiry_date.isnot(None)
        )
    )
    profiles = result.scalars().all()

    count = 0
    doc_fields = [
        ("license_expiry_date",       "athlete.license.expiring_soon",     "Lisans"),
        ("visa_expiry_date",          "athlete.visa.expiring_soon",        "Vize"),
        ("health_report_expiry_date", "athlete.health_report.expiring_soon", "Sağlık raporu"),
    ]

    for ap in profiles:
        for field, event_type, label in doc_fields:
            expiry: Optional[date] = getattr(ap, field)
            if expiry is None:
                continue
            if expiry > cutoff:
                continue  # henüz uyarı eşiğine girmedi
            days_left = (expiry - today).days
            added = await _insert_event_if_new(
                db,
                club_id=ap.club_id,
                event_type=event_type,
                aggregate_type="athlete_profile",
                aggregate_id=str(ap.person_id),
                payload={
                    "person_id": str(ap.person_id),
                    "doc_label": label,
                    "expiry_date": str(expiry),
                    "days_remaining": days_left,
                },
                scheduled_for=sf,
            )
            if added:
                count += 1

    logger.info("scan_athlete_docs: %d yeni event", count)
    return count


async def scan_sessions_tomorrow(db: AsyncSession) -> int:
    """Yarın gerçekleşecek eğitim oturumları."""
    from app.models.training import TrainingSession
    from sqlalchemy.orm import selectinload

    today = date.today()
    tomorrow = today + timedelta(days=1)
    sf = _day_start(today)

    result = await db.execute(
        select(TrainingSession)
        .options(selectinload(TrainingSession.course))
        .where(
            TrainingSession.session_date == tomorrow,
            TrainingSession.status != "iptal",
        )
    )
    sessions = result.scalars().all()

    count = 0
    for s in sessions:
        added = await _insert_event_if_new(
            db,
            club_id=s.club_id,
            event_type="training.session.starts_tomorrow",
            aggregate_type="training_session",
            aggregate_id=str(s.id),
            payload={
                "course_id": str(s.course_id),
                "course_name": s.course.name if s.course else None,
                "session_date": str(s.session_date),
                "start_time": str(s.start_time) if s.start_time else None,
            },
            scheduled_for=sf,
        )
        if added:
            count += 1

    logger.info("scan_sessions_tomorrow: %d yeni event", count)
    return count


async def run_all_scans(db: AsyncSession) -> dict[str, int]:
    """Tüm nightly scan fonksiyonlarını sırayla çalıştır."""
    results: dict[str, int] = {}
    try:
        results["payment.overdue"] = await scan_overdue_payments(db)
        results["equipment.maintenance.due"] = await scan_maintenance_due(db)
        results["equipment.insurance.expiring_soon"] = await scan_insurance_expiring(db)
        results["athlete.docs"] = await scan_athlete_docs(db)
        results["training.session.starts_tomorrow"] = await scan_sessions_tomorrow(db)
        await db.commit()
        total = sum(results.values())
        logger.info("Nightly scan tamamlandı: %d toplam yeni event %s", total, results)
    except Exception:
        await db.rollback()
        logger.exception("Nightly scan başarısız, rollback yapıldı")
        raise
    return results


# ─────────────────────────────────────────────────────────────────────────────
# 3. E-posta dispatch (Sprint 15B — delivery tabanlı)
# ─────────────────────────────────────────────────────────────────────────────

async def dispatch_pending_events(db: AsyncSession) -> dict[str, int]:
    """Pending event'ler için delivery kayıtları oluştur, ardından gönder.

    Sprint 15B ile birlikte bu fonksiyon iki aşamada çalışır:
      1. Pending event'ler için resolve_recipients() → notification_deliveries INSERT
      2. Pending delivery'leri gönder (retry + backoff delivery seviyesinde)

    Geriye dönük uyumluluk: dönen dict anahtar isimleri güncellendi:
      "dispatched" → "sent"
      "skipped"    → "retrying"
      "failed"     → "failed"
    Eski callers (notifications router, scheduler) bu dict'i yalnızca loglama
    amacıyla kullanır; key değişikliği breaking change değildir.
    """
    from sqlalchemy import or_

    from app.config import get_settings
    from app.services.notification_service import (
        create_deliveries_for_event,
        dispatch_pending_deliveries,
    )

    # ── Guard: SMTP tanımlı değilse dispatch'i çalıştırma ────────────────────
    _settings = get_settings()
    if not _settings.smtp_host:
        logger.warning(
            "dispatch_pending_events: SMTP_HOST tanımlı değil — atlandı. "
            "Eventler 'pending' kalacak."
        )
        return {"sent": 0, "failed": 0, "retrying": 0}

    today = date.today()
    now_naive = datetime.utcnow()

    # ── Aşama 1: Delivery kayıtları oluştur ──────────────────────────────────
    # Bugünün yeni event'leri için alıcı çöz ve delivery satırları aç.
    # Idempotent: varolan kayıtlar UNIQUE constraint ile atlanır.
    new_events_stmt = (
        select(DomainEvent)
        .where(
            DomainEvent.status == "pending",
            DomainEvent.processed_at.is_(None),
            func.date(DomainEvent.created_at) == today,
        )
        .order_by(DomainEvent.created_at)
        .limit(200)
    )
    new_events = (await db.execute(new_events_stmt)).scalars().all()

    total_new_deliveries = 0
    for event in new_events:
        try:
            n = await create_deliveries_for_event(event, db)
            total_new_deliveries += n
            if n == 0:
                # Alıcı bulunamadı → event'i failed yap
                event.status = "failed"
                event.processed_at = datetime.now(tz=timezone.utc)
                event.last_error = "Alıcı bulunamadı: resolve_recipients boş döndü"
                logger.error(
                    "dispatch: alıcı yok, event failed: type=%s event_id=%s",
                    event.event_type, event.id,
                )
        except Exception:
            logger.exception(
                "dispatch: delivery oluşturma hatası event_id=%s", event.id
            )

    if total_new_deliveries > 0 or new_events:
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("dispatch_pending_events: delivery commit hatası")
            raise

    # ── Aşama 2: Delivery'leri gönder ────────────────────────────────────────
    result = await dispatch_pending_deliveries(db)

    logger.info(
        "dispatch_pending_events: %d delivery oluşturuldu; "
        "gönderim: %d gönderildi, %d başarısız, %d retry",
        total_new_deliveries,
        result["sent"], result["failed"], result["retrying"],
    )
    return result
