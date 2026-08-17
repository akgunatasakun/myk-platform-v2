"""Bildirim servisi — recipient resolver + delivery dispatcher (Sprint 15B).

İki sorumluluk:
  1. resolve_recipients(event, db) → alıcı listesi [(person_id|None, email)]
     Event tipine göre doğru kişi(ler)in e-postasını döndürür.

  2. dispatch_pending_deliveries(db) → dict[str, int]
     notification_deliveries tablosundaki pending kayıtları gönderir;
     retry + backoff, kısmi başarı ve event tamamlama mantığını yönetir.

Recipient politikası:
  payment.overdue                   → ödeme sahibi kişi (person_id → email)
  athlete.license/visa/health.*     → sporcunun opt-in velileri
  training.session.starts_tomorrow  → kursa kayıtlı sporcuların opt-in velileri
  equipment.*                       → kulüp yönetim e-postası (person=None)
  payment.created                   → kulüp yönetim e-postası
  application.*                     → zaten doğrudan gönderiliyor; buraya gelmez
  bilinmeyen                        → kulüp yönetim e-postası

Alıcı e-posta çözümleme önceliği:
  Person.email → yoksa User.email (person_id = person.id olan kullanıcı)
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import asyncio

from sqlalchemy import select, text, update as sa_update, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

# SQLite ortamı (testler) için modül geneli asyncio lock.
# PostgreSQL'de DB-native FOR UPDATE SKIP LOCKED kullanıldığından bu lock'a
# gerek yoktur; varlığı üretimi etkilemez.
_sqlite_claim_lock: asyncio.Lock | None = None


def _get_sqlite_lock() -> asyncio.Lock:
    global _sqlite_claim_lock
    if _sqlite_claim_lock is None:
        _sqlite_claim_lock = asyncio.Lock()
    return _sqlite_claim_lock

from app.models.events import DomainEvent
from app.models.notification_delivery import NotificationDelivery

logger = logging.getLogger(__name__)

# ── Delivery retry sabitleri ──────────────────────────────────────────────────
MAX_DELIVERY_ATTEMPTS = 3
BACKOFF_MINUTES = [5, 25]       # deneme 1→+5dk, deneme 2→+25dk, 3→kalıcı fail
CLAIM_TIMEOUT_MINUTES = 10      # bu süreden uzun claim → crash recovery


# ── Alıcı veri yapısı ─────────────────────────────────────────────────────────

@dataclass
class Recipient:
    email: str
    person_id: Optional[uuid.UUID] = None


# ─────────────────────────────────────────────────────────────────────────────
# 1. Recipient Resolver
# ─────────────────────────────────────────────────────────────────────────────

async def _person_email(person_id: uuid.UUID, db: AsyncSession) -> Optional[str]:
    """Person.email → yoksa ilgili User.email döndürür."""
    from app.models.person import Person
    from app.models.user import User

    person = await db.get(Person, person_id)
    if not person:
        return None
    if person.email and person.email.strip():
        return person.email.strip()

    # Person'a bağlı User'ın e-postasına dön
    result = await db.execute(
        select(User.email).where(
            User.person_id == person_id,
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        ).limit(1)
    )
    user_email = result.scalar_one_or_none()
    return user_email


async def _guardian_recipients(
    athlete_person_id: uuid.UUID, db: AsyncSession
) -> List[Recipient]:
    """Sporcunun can_receive_notifications=True olan velilerini döndürür."""
    from app.models.person_guardian import PersonGuardian

    result = await db.execute(
        select(PersonGuardian).where(
            PersonGuardian.athlete_person_id == athlete_person_id,
            PersonGuardian.can_receive_notifications.is_(True),
        )
    )
    links = result.scalars().all()

    recipients: List[Recipient] = []
    for link in links:
        email = await _person_email(link.guardian_person_id, db)
        if email:
            recipients.append(Recipient(email=email, person_id=link.guardian_person_id))
        else:
            logger.warning(
                "recipient_resolver: veli için e-posta bulunamadı person_id=%s",
                link.guardian_person_id,
            )
    return recipients


async def _enrolled_athlete_guardian_recipients(
    course_id: uuid.UUID, club_id: uuid.UUID, db: AsyncSession
) -> List[Recipient]:
    """Kursa aktif kayıtlı sporcuların opt-in velilerini döndürür (tekrarsız)."""
    from app.models.training import TrainingEnrollment

    enrollments_result = await db.execute(
        select(TrainingEnrollment.person_id).where(
            TrainingEnrollment.course_id == course_id,
            TrainingEnrollment.status == "active",
            TrainingEnrollment.is_deleted.is_(False),
        )
    )
    athlete_ids = [row[0] for row in enrollments_result.all()]

    seen_emails: set[str] = set()
    recipients: List[Recipient] = []
    for athlete_id in athlete_ids:
        for r in await _guardian_recipients(athlete_id, db):
            if r.email not in seen_emails:
                seen_emails.add(r.email)
                recipients.append(r)
    return recipients


async def _club_admin_recipient(
    club_id: uuid.UUID, db: AsyncSession
) -> Optional[Recipient]:
    """Kulüp ayarlarındaki genel e-postayı döndürür."""
    from app.models.club import Club
    club = await db.get(Club, club_id)
    if not club:
        return None
    email = (club.settings or {}).get("email", "").strip()
    return Recipient(email=email, person_id=None) if email else None


async def resolve_recipients(
    event: DomainEvent, db: AsyncSession
) -> List[Recipient]:
    """Event tipine göre alıcı listesi döndürür.

    Alıcı bulunamazsa boş liste döner — dispatcher bunu hata olarak loglar.
    """
    p: dict = event.payload or {}
    et = event.event_type

    # ── Ödeme sahibi ──────────────────────────────────────────────────────────
    if et == "payment.overdue":
        person_id_str = p.get("person_id")
        if person_id_str:
            try:
                pid = uuid.UUID(str(person_id_str))
                email = await _person_email(pid, db)
                if email:
                    return [Recipient(email=email, person_id=pid)]
            except (ValueError, AttributeError):
                pass
        # Kişi yoksa veya e-posta bulunamazsa kulüp adminine düş
        logger.warning(
            "resolve_recipients: payment.overdue için kişi e-postası yok, "
            "kulüp adminine yönlendiriliyor. event_id=%s", event.id
        )
        admin = await _club_admin_recipient(event.club_id, db)
        return [admin] if admin else []

    # ── Sporcu belgeleri ──────────────────────────────────────────────────────
    if et in (
        "athlete.license.expiring_soon",
        "athlete.visa.expiring_soon",
        "athlete.health_report.expiring_soon",
    ):
        person_id_str = p.get("person_id")
        if person_id_str:
            try:
                pid = uuid.UUID(str(person_id_str))
                recipients = await _guardian_recipients(pid, db)
                if recipients:
                    return recipients
            except (ValueError, AttributeError):
                pass
        logger.warning(
            "resolve_recipients: %s için veli e-postası yok, "
            "kulüp adminine yönlendiriliyor. event_id=%s", et, event.id
        )
        admin = await _club_admin_recipient(event.club_id, db)
        return [admin] if admin else []

    # ── Yarınki eğitim oturumu ────────────────────────────────────────────────
    if et == "training.session.starts_tomorrow":
        course_id_str = p.get("course_id")
        if course_id_str:
            try:
                cid = uuid.UUID(str(course_id_str))
                recipients = await _enrolled_athlete_guardian_recipients(
                    cid, event.club_id, db
                )
                if recipients:
                    return recipients
            except (ValueError, AttributeError):
                pass
        # Kayıtlı sporcu yoksa veya veli e-postası bulunamazsa kulüp adminine
        admin = await _club_admin_recipient(event.club_id, db)
        return [admin] if admin else []

    # ── Ekipman ve genel yönetim olayları → kulüp admini ─────────────────────
    # payment.created, equipment.maintenance.due, equipment.insurance.expiring_soon
    # ve bilinmeyen event tipleri
    admin = await _club_admin_recipient(event.club_id, db)
    return [admin] if admin else []


# ─────────────────────────────────────────────────────────────────────────────
# 2. Delivery Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

async def create_deliveries_for_event(
    event: DomainEvent,
    db: AsyncSession,
) -> int:
    """Event için alıcıları çöz ve notification_deliveries kayıtlarını oluştur.

    Idempotent: UNIQUE constraint sayesinde var olan kayıtlar yeniden oluşturulmaz.
    Döner: oluşturulan yeni delivery sayısı.
    """
    recipients = await resolve_recipients(event, db)

    if not recipients:
        return 0

    bind = await db.connection()
    is_pg = bind.dialect.name == "postgresql"
    created = 0
    for r in recipients:
        if is_pg:
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            result = await db.execute(
                pg_insert(NotificationDelivery)
                .values(
                    id=uuid.uuid4(),
                    club_id=event.club_id,
                    event_id=event.id,
                    recipient_person_id=r.person_id,
                    recipient_email=r.email,
                    channel="email",
                    status="pending",
                    attempt_count=0,
                )
                .on_conflict_do_nothing(
                    index_elements=["event_id", "recipient_email", "channel"]
                )
            )
            if result.rowcount:
                created += 1
            continue

        # Zaten var mı kontrol et (SQLite uyumu için — PG'de ON CONFLICT yeter)
        existing = await db.execute(
            select(NotificationDelivery.id).where(
                NotificationDelivery.event_id == event.id,
                NotificationDelivery.recipient_email == r.email,
                NotificationDelivery.channel == "email",
            ).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            continue  # zaten var

        delivery = NotificationDelivery(
            id=uuid.uuid4(),
            club_id=event.club_id,
            event_id=event.id,
            recipient_person_id=r.person_id,
            recipient_email=r.email,
            channel="email",
            status="pending",
            attempt_count=0,
        )
        db.add(delivery)
        created += 1

    return created


async def _release_stuck_claims(db: AsyncSession, now_naive: datetime) -> int:
    """Crash sonrası takılı kalan claimed delivery'leri serbest bırak.

    processing_since + CLAIM_TIMEOUT_MINUTES geçmiş ve hâlâ claimed olan
    delivery'ler yeniden pending'e alınır (claimed_worker_id = NULL).
    """
    cutoff_naive = now_naive - timedelta(minutes=CLAIM_TIMEOUT_MINUTES)

    result = await db.execute(
        sa_update(NotificationDelivery)
        .where(
            NotificationDelivery.claimed_worker_id.isnot(None),
            NotificationDelivery.status == "pending",
            NotificationDelivery.processing_since.isnot(None),
            NotificationDelivery.processing_since <= cutoff_naive,
        )
        .values(claimed_worker_id=None, processing_since=None)
        .execution_options(synchronize_session=False)
    )
    released: int = result.rowcount if result.rowcount is not None else 0
    if released:
        logger.warning(
            "_release_stuck_claims: %d takılı delivery serbest bırakıldı", released
        )
    return released


async def _claim_batch_pg(
    db: AsyncSession,
    worker_id: str,
    now_naive: datetime,
    batch_size: int = 200,
) -> list:
    """PostgreSQL: FOR UPDATE SKIP LOCKED ile gerçek atomik claim.

    CTE içindeki FOR UPDATE SKIP LOCKED, DB motorunun seçilen satırları
    tek bir statement içinde hem kilitlediğini hem güncellediğini garanti eder.
    Eş zamanlı iki worker aynı satırları asla claim edemez.
    """
    rows = await db.execute(
        text("""
            WITH claimable AS (
                SELECT id
                FROM notification_deliveries
                WHERE claimed_worker_id IS NULL
                  AND status = 'pending'
                  AND attempt_count < :max_attempts
                  AND (next_attempt_at IS NULL OR next_attempt_at <= :now)
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT :batch_size
            )
            UPDATE notification_deliveries AS d
               SET claimed_worker_id = :worker_id,
                   processing_since  = :now
              FROM claimable
             WHERE d.id = claimable.id
            RETURNING d.id
        """),
        {
            "max_attempts": MAX_DELIVERY_ATTEMPTS,
            "now": now_naive,
            "batch_size": batch_size,
            "worker_id": worker_id,
        },
    )
    return [row[0] for row in rows.all()]


async def _claim_batch_sqlite(
    db: AsyncSession,
    worker_id: str,
    now_naive: datetime,
    batch_size: int = 200,
) -> list:
    """SQLite (test ortamı): asyncio.Lock ile seri claim.

    SQLite FOR UPDATE SKIP LOCKED desteklemez. Test ortamında tek event-loop
    üzerinde çalışan asyncio.Lock, iki coroutine'in SELECT + UPDATE döngüsünü
    seri hale getirir ve aynı satırın iki worker tarafından claim edilmesini engeller.
    """
    from sqlalchemy import or_

    lock = _get_sqlite_lock()
    async with lock:
        ids_rows = await db.execute(
            select(NotificationDelivery.id)
            .where(
                NotificationDelivery.claimed_worker_id.is_(None),
                NotificationDelivery.status == "pending",
                NotificationDelivery.attempt_count < MAX_DELIVERY_ATTEMPTS,
                or_(
                    NotificationDelivery.next_attempt_at.is_(None),
                    NotificationDelivery.next_attempt_at <= now_naive,
                ),
            )
            .order_by(NotificationDelivery.created_at)
            .limit(batch_size)
        )
        ids = ids_rows.scalars().all()

        if not ids:
            return []

        await db.execute(
            sa_update(NotificationDelivery)
            .where(NotificationDelivery.id.in_(ids))
            .values(claimed_worker_id=worker_id, processing_since=now_naive)
            .execution_options(synchronize_session=False)
        )
        await db.commit()
        return list(ids)


async def dispatch_pending_deliveries(db: AsyncSession) -> dict[str, int]:
    """Pending delivery'leri gönder; retry + backoff uygula.

    Concurrent safety:
      PostgreSQL: FOR UPDATE SKIP LOCKED ile DB-native atomik claim.
      SQLite (test): asyncio.Lock ile seri claim.
      Her iki durumda da aynı delivery iki ayrı worker'a verilmez.

    Crash recovery:
      Dispatch başında processing_since + CLAIM_TIMEOUT_MINUTES geçmiş claimler
      serbest bırakılır.

    Event tamamlama:
      Tüm delivery'ler terminal (done/failed) olunca event.status = 'done'.

    Döner: {"sent": N, "failed": N, "retrying": N}
    """
    from app.config import get_settings
    from app.services.email_service import dispatch_domain_event_email

    _cfg = get_settings()
    if not _cfg.smtp_host:
        logger.warning(
            "dispatch_pending_deliveries: SMTP_HOST tanımlı değil — atlandı."
        )
        return {"sent": 0, "failed": 0, "retrying": 0}

    now = datetime.now(tz=timezone.utc)
    now_naive = datetime.utcnow()
    worker_id = str(uuid.uuid4())
    results: dict[str, int] = {"sent": 0, "failed": 0, "retrying": 0}

    # ── Crash recovery: takılı claimler serbest bırak + commit ───────────────
    await _release_stuck_claims(db, now_naive)
    await db.commit()

    # ── Atomik claim: dialect'e göre doğru mekanizma seç ─────────────────────
    conn = await db.connection()
    is_pg = conn.dialect.name == "postgresql"

    if is_pg:
        claimed_ids = await _claim_batch_pg(db, worker_id, now_naive)
        await db.commit()
    else:
        claimed_ids = await _claim_batch_sqlite(db, worker_id, now_naive)
        # commit _claim_batch_sqlite içinde yapıldı

    if not claimed_ids:
        logger.info("dispatch_pending_deliveries: işlenecek delivery yok")
        return results

    # ── Yalnızca bu worker'ın claimlerini çek ─────────────────────────────────
    stmt = (
        select(NotificationDelivery)
        .where(NotificationDelivery.id.in_(claimed_ids))
        .order_by(NotificationDelivery.created_at)
    )
    deliveries = (await db.execute(stmt)).scalars().all()

    if not deliveries:
        logger.info("dispatch_pending_deliveries: işlenecek delivery yok")
        return results

    # Event önbelleği — aynı event'i defalarca yüklememek için
    event_cache: dict[uuid.UUID, DomainEvent] = {}

    for delivery in deliveries:
        event = event_cache.get(delivery.event_id)
        if event is None:
            event = await db.get(DomainEvent, delivery.event_id)
            if event is None:
                logger.error(
                    "dispatch_pending_deliveries: event bulunamadı event_id=%s",
                    delivery.event_id,
                )
                delivery.status = "failed"
                delivery.last_error = "Bağlı event bulunamadı"
                delivery.claimed_worker_id = None
                delivery.processing_since = None
                results["failed"] += 1
                continue
            event_cache[delivery.event_id] = event

        try:
            await dispatch_domain_event_email(event, delivery.recipient_email)
            delivery.status = "done"
            delivery.sent_at = now
            delivery.attempt_count += 1
            delivery.claimed_worker_id = None    # claim serbest bırak
            delivery.processing_since = None
            results["sent"] += 1
            logger.debug(
                "dispatch: gönderildi to=%s event=%s attempt=%d",
                delivery.recipient_email, event.event_type, delivery.attempt_count,
            )
        except Exception as exc:
            delivery.attempt_count += 1
            delivery.last_error = str(exc)[:500]
            delivery.claimed_worker_id = None    # claim serbest bırak (retry veya fail)
            delivery.processing_since = None

            if delivery.attempt_count >= MAX_DELIVERY_ATTEMPTS:
                delivery.status = "failed"
                logger.error(
                    "dispatch: max deneme aşıldı to=%s event=%s error=%s",
                    delivery.recipient_email, event.event_type, delivery.last_error,
                )
                results["failed"] += 1
            else:
                backoff_idx = delivery.attempt_count - 1
                backoff_min = (
                    BACKOFF_MINUTES[backoff_idx]
                    if backoff_idx < len(BACKOFF_MINUTES)
                    else BACKOFF_MINUTES[-1]
                )
                delivery.next_attempt_at = now + timedelta(minutes=backoff_min)
                logger.warning(
                    "dispatch: retry planlandı +%ddk to=%s event=%s attempt=%d/%d",
                    backoff_min, delivery.recipient_email,
                    event.event_type, delivery.attempt_count, MAX_DELIVERY_ATTEMPTS,
                )
                results["retrying"] += 1

    # ── Event tamamlama: tüm delivery'ler terminal mi? ────────────────────────
    await _finalize_completed_events(list(event_cache.values()), now, db)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("dispatch_pending_deliveries: commit başarısız")
        raise

    logger.info(
        "dispatch_pending_deliveries: %d gönderildi, %d başarısız, %d retry",
        results["sent"], results["failed"], results["retrying"],
    )
    return results


async def _finalize_completed_events(
    events: list[DomainEvent],
    now: datetime,
    db: AsyncSession,
) -> None:
    """Tüm delivery'leri terminal olan event'leri done işaretle."""
    for event in events:
        if event.status == "done":
            continue  # zaten tamamlanmış

        pending_count_r = await db.execute(
            select(sa_func.count(NotificationDelivery.id)).where(
                NotificationDelivery.event_id == event.id,
                NotificationDelivery.status == "pending",
            )
        )
        pending_count: int = pending_count_r.scalar_one()

        if pending_count == 0:
            # Tüm delivery'ler terminal → event done
            event.status = "done"
            event.processed_at = now
            logger.info(
                "event tamamlandı: event_id=%s type=%s",
                event.id, event.event_type,
            )
