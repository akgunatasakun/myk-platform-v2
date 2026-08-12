"""APScheduler — nightly domain event scanner.

Mimari kararlar:
  - AsyncIOScheduler kullanılır (FastAPI'nin asyncio event loop'u ile aynı).
  - Production'da birden fazla API replica çalışıyorsa her biri bu scheduler'ı
    başlatır. Duplicate çalışmayı önlemek için nightly job başında
    PostgreSQL advisory lock alınır.
  - Advisory lock key: 0xMYK_SCAN = 0x4D594B5F5343414E = 5566064065367891022
    (değişmez sabit; replica'lar aynı lock'u kapışır, yalnızca biri devam eder)
  - SQLite test ortamında advisory lock yoktur; lock fonksiyonu True döner.
  - Scheduler, FastAPI lifespan'de start/shutdown edilir.
"""
from __future__ import annotations

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

# PostgreSQL advisory lock sabit anahtarı
_ADVISORY_LOCK_KEY = 5566064065367891022  # 0x4D594B5F5343414E

scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    """Singleton scheduler nesnesi."""
    global scheduler
    if scheduler is None:
        scheduler = AsyncIOScheduler(timezone="Europe/Istanbul")
    return scheduler


async def _try_advisory_lock(db) -> bool:
    """PostgreSQL advisory lock dene. Sadece bir replica devam eder.
    SQLite'ta her zaman True döner (test ortamı)."""
    from sqlalchemy import text

    try:
        conn = await db.connection()
        if conn.dialect.name != "postgresql":
            return True
        result = await db.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": _ADVISORY_LOCK_KEY},
        )
        locked: bool = result.scalar_one()
        if not locked:
            logger.info("Advisory lock alınamadı — başka replica çalışıyor, scan atlanıyor")
        return locked
    except Exception:
        logger.exception("Advisory lock kontrolü başarısız — scan yine de çalışacak")
        return True


async def _release_advisory_lock(db) -> None:
    """Advisory lock serbest bırak."""
    from sqlalchemy import text

    try:
        conn = await db.connection()
        if conn.dialect.name != "postgresql":
            return
        await db.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": _ADVISORY_LOCK_KEY},
        )
    except Exception:
        logger.warning("Advisory lock release başarısız (önemsiz)")


async def nightly_event_scan() -> None:
    """Tüm domain scan fonksiyonlarını çalıştır.

    Çağrı zinciri: APScheduler → bu fonksiyon → event_service.run_all_scans()
    """
    from app.database import AsyncSessionLocal
    from app.services.event_service import run_all_scans

    logger.info("Nightly event scan başladı")
    async with AsyncSessionLocal() as db:
        locked = await _try_advisory_lock(db)
        if not locked:
            return
        try:
            await run_all_scans(db)
        finally:
            await _release_advisory_lock(db)

    logger.info("Nightly event scan bitti")


async def email_dispatch_job() -> None:
    """Bugün oluşturulan pending event'leri kulüp e-postasına gönder.

    Çağrı zinciri: APScheduler (02:05) → bu fonksiyon → event_service.dispatch_pending_events()
    Scan'den 5 dakika sonra çalışır; yeni event'lerin commit edilmesi için yeterli süre.
    """
    from app.database import AsyncSessionLocal
    from app.services.event_service import dispatch_pending_events

    logger.info("Email dispatch job başladı")
    async with AsyncSessionLocal() as db:
        locked = await _try_advisory_lock(db)
        if not locked:
            logger.info("Email dispatch: advisory lock alınamadı, atlanıyor")
            return
        try:
            results = await dispatch_pending_events(db)
            logger.info(
                "Email dispatch tamamlandı: %d gönderildi, %d başarısız",
                results.get("dispatched", 0),
                results.get("failed", 0),
            )
        except Exception:
            logger.exception("Email dispatch job başarısız")
        finally:
            await _release_advisory_lock(db)

    logger.info("Email dispatch job bitti")


def setup_scheduler() -> AsyncIOScheduler:
    """Scheduler'ı yapılandır ve döndür (henüz başlatma)."""
    sched = get_scheduler()

    # Mevcut jobları kaldır (hot-reload güvenliği)
    for job_id in ("nightly_scan", "email_dispatch"):
        if sched.get_job(job_id):
            sched.remove_job(job_id)

    sched.add_job(
        nightly_event_scan,
        trigger="cron",
        hour=2,
        minute=0,
        id="nightly_scan",
        name="Nightly Domain Event Scanner",
        misfire_grace_time=3600,
        coalesce=True,
        max_instances=1,
    )

    sched.add_job(
        email_dispatch_job,
        trigger="cron",
        hour=2,
        minute=5,
        id="email_dispatch",
        name="Email Dispatch for Domain Events",
        misfire_grace_time=3600,
        coalesce=True,
        max_instances=1,
    )

    logger.info(
        "APScheduler yapılandırıldı "
        "(nightly_scan 02:00, email_dispatch 02:05 Europe/Istanbul)"
    )
    return sched
