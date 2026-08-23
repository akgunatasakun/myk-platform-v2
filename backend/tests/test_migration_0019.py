"""
Migration 0019 testleri — users.must_change_password

Sadece PostgreSQL ortamında çalışır.

Çalıştırma:
  DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db \\
    pytest tests/test_migration_0019.py -v

Test kapsamı:
  1. Upgrade: must_change_password kolonu oluşur (NOT NULL, DEFAULT FALSE).
  2. Backfill: person_id bağlı ve persons.must_change_password=TRUE olan
     User kayıtları User.must_change_password=TRUE yapılır.
  3. Backfill bağımsızlığı: person_id=NULL olan User dokunulmaz.
  4. Backfill seçiciliği: persons.must_change_password=FALSE olan User
     FALSE kalır.
  5. Silinmiş User (is_deleted=TRUE) backfill'e dahil edilmez.
  6. Downgrade: must_change_password kolonu kaldırılır; persons tablosu etkilenmez.
"""
import os
import subprocess
import sys
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# ── Ortam ─────────────────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
IS_POSTGRES = DATABASE_URL.startswith("postgresql")

pytestmark = pytest.mark.skipif(
    not IS_POSTGRES,
    reason="Bu testler sadece PostgreSQL ortamında çalışır (DATABASE_URL=postgresql+asyncpg://...)",
)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def run_alembic(*args: str) -> str:
    result = subprocess.run(
        ["alembic", "-c", "migrations/alembic.ini", *args],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": DATABASE_URL},
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(
            f"alembic {' '.join(args)} başarısız (exit {result.returncode}):\n{result.stderr}"
        )
    return result.stdout


@pytest_asyncio.fixture(scope="module")
async def engine():
    eng = create_async_engine(DATABASE_URL, echo=False)
    yield eng
    await eng.dispose()


# ── Veri yardımcıları ─────────────────────────────────────────────────────────

async def _insert_club(conn, club_id: uuid.UUID) -> None:
    await conn.execute(text("""
        INSERT INTO clubs (id, slug, name, plan, is_active)
        VALUES (:id, :slug, 'MIG019 Test Kulübü', 'starter', true)
        ON CONFLICT DO NOTHING
    """), {"id": club_id, "slug": f"mig019-{club_id.hex[:8]}"})


async def _insert_person(
    conn, person_id: uuid.UUID, club_id: uuid.UUID, must_change: bool
) -> None:
    await conn.execute(text("""
        INSERT INTO persons (id, club_id, first_name, last_name, must_change_password)
        VALUES (:id, :club_id, 'Test', 'Kisi', :mcp)
        ON CONFLICT DO NOTHING
    """), {"id": person_id, "club_id": club_id, "mcp": must_change})


async def _insert_user(
    conn,
    user_id: uuid.UUID,
    club_id: uuid.UUID,
    person_id: uuid.UUID | None,
    is_deleted: bool = False,
) -> None:
    await conn.execute(text("""
        INSERT INTO users (id, club_id, email, password_hash, full_name, role,
                           is_active, is_deleted, person_id)
        VALUES (:id, :club_id, :email, 'hash', 'Test User', 'uye',
                true, :is_deleted, :person_id)
        ON CONFLICT DO NOTHING
    """), {
        "id": user_id,
        "club_id": club_id,
        "email": f"mig019-{user_id.hex[:8]}@test.invalid",
        "is_deleted": is_deleted,
        "person_id": person_id,
    })


# ── 1. Kolon upgrade testi ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_0019_column_exists_after_upgrade(engine):
    """Upgrade sonrası users.must_change_password kolonu NOT NULL DEFAULT FALSE olmalı."""
    run_alembic("upgrade", "head")
    async with engine.connect() as conn:
        r = await conn.execute(text("""
            SELECT column_name, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'users'
              AND column_name = 'must_change_password'
        """))
        row = r.fetchone()
    assert row is not None, "users.must_change_password kolonu bulunamadı (0019 çalışmadı?)"
    assert row[2] == "NO", "must_change_password nullable olmamalı (NOT NULL)"
    assert "false" in (row[1] or "").lower(), (
        f"Varsayılan değer 'false' olmalı, alınan: {row[1]!r}"
    )


# ── 2. Backfill testi ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_0019_backfill_from_person(engine):
    """person.must_change_password=TRUE olan bağlı aktif User backfill edilmeli."""
    club_id = uuid.uuid4()
    person_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # 0018'e downgrade et
    run_alembic("downgrade", "0018")

    async with engine.begin() as conn:
        await _insert_club(conn, club_id)
        await _insert_person(conn, person_id, club_id, must_change=True)
        await _insert_user(conn, user_id, club_id, person_id)

    # 0019'a upgrade → backfill çalışır
    run_alembic("upgrade", "0019")

    async with engine.connect() as conn:
        r = await conn.execute(
            text("SELECT must_change_password FROM users WHERE id = :id"),
            {"id": user_id},
        )
        row = r.fetchone()

    # Temizlik
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM clubs WHERE id = :id"), {"id": club_id})

    run_alembic("upgrade", "head")

    assert row is not None, "Test kullanıcısı bulunamadı"
    assert row[0] is True, (
        "Backfill başarısız: person.must_change_password=TRUE iken "
        "user.must_change_password FALSE kaldı"
    )


# ── 3. Person bağlantısı yoksa dokunulmamalı ─────────────────────────────────

@pytest.mark.asyncio
async def test_0019_backfill_skips_person_null(engine):
    """person_id=NULL olan User'ın must_change_password değeri FALSE kalmalı."""
    club_id = uuid.uuid4()
    user_id = uuid.uuid4()

    run_alembic("downgrade", "0018")

    async with engine.begin() as conn:
        await _insert_club(conn, club_id)
        await _insert_user(conn, user_id, club_id, person_id=None)

    run_alembic("upgrade", "0019")

    async with engine.connect() as conn:
        r = await conn.execute(
            text("SELECT must_change_password FROM users WHERE id = :id"),
            {"id": user_id},
        )
        row = r.fetchone()

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM clubs WHERE id = :id"), {"id": club_id})

    run_alembic("upgrade", "head")

    assert row is not None
    assert row[0] is False, (
        "person_id=NULL olan User backfill'e dahil edilmemeli; "
        "must_change_password FALSE kalmalı"
    )


# ── 4. Person.must_change_password=FALSE ise User da FALSE kalmalı ────────────

@pytest.mark.asyncio
async def test_0019_backfill_skips_person_false(engine):
    """person.must_change_password=FALSE olan bağlı User FALSE kalmalı."""
    club_id = uuid.uuid4()
    person_id = uuid.uuid4()
    user_id = uuid.uuid4()

    run_alembic("downgrade", "0018")

    async with engine.begin() as conn:
        await _insert_club(conn, club_id)
        await _insert_person(conn, person_id, club_id, must_change=False)
        await _insert_user(conn, user_id, club_id, person_id)

    run_alembic("upgrade", "0019")

    async with engine.connect() as conn:
        r = await conn.execute(
            text("SELECT must_change_password FROM users WHERE id = :id"),
            {"id": user_id},
        )
        row = r.fetchone()

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM clubs WHERE id = :id"), {"id": club_id})

    run_alembic("upgrade", "head")

    assert row is not None
    assert row[0] is False, (
        "person.must_change_password=FALSE iken user.must_change_password TRUE yapılmamalı"
    )


# ── 5. Silinmiş User backfill'e dahil edilmemeli ─────────────────────────────

@pytest.mark.asyncio
async def test_0019_backfill_skips_deleted_user(engine):
    """is_deleted=TRUE olan User person.must_change_password=TRUE olsa bile güncellenmemeli."""
    club_id = uuid.uuid4()
    person_id = uuid.uuid4()
    user_id = uuid.uuid4()

    run_alembic("downgrade", "0018")

    async with engine.begin() as conn:
        await _insert_club(conn, club_id)
        await _insert_person(conn, person_id, club_id, must_change=True)
        await _insert_user(conn, user_id, club_id, person_id, is_deleted=True)

    run_alembic("upgrade", "0019")

    async with engine.connect() as conn:
        r = await conn.execute(
            text("SELECT must_change_password FROM users WHERE id = :id"),
            {"id": user_id},
        )
        row = r.fetchone()

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM clubs WHERE id = :id"), {"id": club_id})

    run_alembic("upgrade", "head")

    assert row is not None
    assert row[0] is False, (
        "is_deleted=TRUE olan User backfill'e dahil edilmemeli; must_change_password FALSE kalmalı"
    )


# ── 6. Downgrade testi ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_0019_downgrade_removes_column(engine):
    """0019 downgrade → must_change_password kolonu users'dan kaldırılmalı."""
    run_alembic("downgrade", "0018")
    try:
        async with engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'users'
                  AND column_name = 'must_change_password'
            """))
            row = r.fetchone()
        assert row is None, (
            "Downgrade sonrası users.must_change_password kolonu hâlâ var"
        )

        # persons.must_change_password dokunulmamış olmalı
        async with engine.connect() as conn:
            r2 = await conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'persons'
                  AND column_name = 'must_change_password'
            """))
            row2 = r2.fetchone()
        assert row2 is not None, (
            "Downgrade yanlışlıkla persons.must_change_password'u kaldırdı — dokunulmamalıydı"
        )
    finally:
        run_alembic("upgrade", "head")


# ── 7. Upgrade/downgrade/upgrade döngüsü (idempotency) ───────────────────────

def test_0019_upgrade_downgrade_upgrade_idempotent():
    """head → downgrade 0018 → upgrade head tekrar sorunsuz çalışmalı."""
    run_alembic("downgrade", "0018")
    run_alembic("upgrade", "head")
