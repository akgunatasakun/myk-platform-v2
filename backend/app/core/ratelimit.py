"""Redis tabanlı rate limiter — brute-force koruması."""
import hashlib
import logging

import redis.asyncio as aioredis

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Login rate limit: pencere ve maksimum deneme
WINDOW_SECONDS = 900   # 15 dakika
MAX_ATTEMPTS = 10


def _make_key(club_slug: str, email: str, ip: str) -> str:
    """Tenant + email + IP bileşik anahtar (hash ile)."""
    raw = f"{club_slug}:{email.lower()}:{ip}"
    return "rl:" + hashlib.sha256(raw.encode()).hexdigest()[:32]


async def check_rate_limit(
    redis_client: aioredis.Redis,
    club_slug: str,
    email: str,
    ip: str,
) -> tuple[bool, int]:
    """
    (izin_var, retry_after_saniye) döndürür.
    izin_var=False ise giriş engellenmeli.
    """
    try:
        key = _make_key(club_slug, email, ip)
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, WINDOW_SECONDS)
        if count > MAX_ATTEMPTS:
            ttl = await redis_client.ttl(key)
            return False, max(ttl, 0)
        return True, 0
    except Exception as e:
        logger.warning(f"Rate limit Redis hatası (izin verildi): {e}")
        return True, 0  # Redis yoksa engelleme yapma


async def reset_rate_limit(
    redis_client: aioredis.Redis,
    club_slug: str,
    email: str,
    ip: str,
) -> None:
    """Başarılı girişte sayacı sıfırla."""
    try:
        key = _make_key(club_slug, email, ip)
        await redis_client.delete(key)
    except Exception as e:
        logger.warning(f"Rate limit sıfırlama hatası: {e}")


async def get_redis() -> aioredis.Redis:
    """FastAPI bağımlılığı."""
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()
