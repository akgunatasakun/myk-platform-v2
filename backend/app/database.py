"""MYK Platform V2 — Veritabanı Bağlantısı (SQLAlchemy 2 async)"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

_is_sqlite = settings.database_url.startswith("sqlite")

_engine_kwargs: dict = {
    "echo": settings.myk_env == "development",
}
if not _is_sqlite:
    # SQLite StaticPool'da pool_size / max_overflow desteklenmez
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10

engine = create_async_engine(settings.database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Tüm SQLAlchemy modellerinin temel sınıfı."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI bağımlılığı: her istek için DB oturumu."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
