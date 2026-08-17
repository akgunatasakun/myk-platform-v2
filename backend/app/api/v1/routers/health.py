"""Health check endpoint."""
import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.database import get_db
from app.core.ratelimit import get_redis

router = APIRouter(prefix="/health", tags=["health"])

_start_time = time.time()


@router.get("")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> dict:
    """
    Sistem sağlık kontrolü.
    200 → tüm bileşenler sağlıklı.
    503 → en az bir bileşen hatalı.
    """
    status: dict = {
        "status": "ok",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "components": {},
    }
    ok = True

    # PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        status["components"]["postgres"] = "ok"
    except Exception as e:
        status["components"]["postgres"] = f"error: {e}"
        ok = False

    # Redis
    try:
        await redis_client.ping()
        status["components"]["redis"] = "ok"
    except Exception as e:
        status["components"]["redis"] = f"error: {e}"
        ok = False

    # SMTP yapılandırma durumu — değer değil, yalnızca bool
    from app.config import get_settings
    _cfg = get_settings()
    status["components"]["smtp_configured"] = bool(_cfg.smtp_host)

    if not ok:
        status["status"] = "degraded"
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content=status)

    return status
