"""pytest konfigürasyonu — async test altyapısı."""
import asyncio
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models.club import Club
from app.models.user import User

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
_TestSession = async_sessionmaker(_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with _TestSession() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ─── Ortak test verileri ───────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_club(db_session: AsyncSession) -> Club:
    # Her test için benzersiz slug — paralel/sıralı testlerde slug çakışması olmaz
    slug = f"test-kulup-{uuid.uuid4().hex[:8]}"
    club = Club(
        id=uuid.uuid4(),
        slug=slug,
        name="Test Yelken Kulübü",
        plan="starter",
        is_active=True,
        settings={},
    )
    db_session.add(club)
    await db_session.flush()   # commit değil; session rollback'i geri alır
    return club


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_club: Club) -> User:
    user = User(
        id=uuid.uuid4(),
        club_id=test_club.id,
        email=f"yonetici-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("Gizli1234!"),
        full_name="Test Yönetici",
        role="kulup_yonetici",
        is_active=True,
        is_deleted=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def sporcu_user(db_session: AsyncSession, test_club: Club) -> User:
    user = User(
        id=uuid.uuid4(),
        club_id=test_club.id,
        email=f"sporcu-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("Sporcu5678!"),
        full_name="Test Sporcu",
        role="sporcu",
        is_active=True,
        is_deleted=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
def yonetici_token(test_club: Club, test_user: User) -> str:
    return create_access_token(str(test_user.id), str(test_club.id), test_user.role)


@pytest_asyncio.fixture
def sporcu_token(test_club: Club, sporcu_user: User) -> str:
    return create_access_token(str(sporcu_user.id), str(test_club.id), sporcu_user.role)


@pytest.fixture
def session_factory():
    """Test DB session factory — concurrent dispatch testleri için iki ayrı session açar."""
    return _TestSession
