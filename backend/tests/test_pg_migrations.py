"""
PostgreSQL migration testleri.

Sadece PostgreSQL ortamında çalışır — DATABASE_URL postgresql ile başlamazsa atlanır.
SQLite birim testleri ayrı çalışmaya devam eder; bu testler migration doğruluğunu
gerçek PostgreSQL üzerinde garantilemek için eklendi.

Tetikleyici: migration 0017'de sa.Text() → UUID FK tip uyumsuzluğu SQLite tarafından
yakalanmadı; production'da alembic hatası verdi.

Çalıştırma:
  DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db \\
    pytest tests/test_pg_migrations.py -v
"""
import asyncio
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

# Backend kök dizini (bu dosyanın bir üstü)
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def run_alembic(*args: str) -> str:
    """alembic komutunu backend/ dizininden çalıştırır; hata varsa RuntimeError."""
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


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="module")
async def engine():
    e = create_async_engine(DATABASE_URL, echo=False)
    yield e
    await e.dispose()


# ── 1. Boş DB → head ─────────────────────────────────────────────────────────

def test_fresh_upgrade_head():
    """Boş PostgreSQL DB'den alembic upgrade head başarıyla tamamlanmalı."""
    run_alembic("upgrade", "head")


@pytest.mark.asyncio
async def test_current_revision_is_head(engine):
    """Migration sonrası alembic_version = '0020' (head) olmalı."""
    async with engine.connect() as conn:
        r = await conn.execute(text("SELECT version_num FROM alembic_version"))
        rev = r.scalar_one()
    assert rev == "0022", f"Beklenen '0022', alınan '{rev!r}'"


# ── 2. Şema doğrulama ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_junction_tables_exist(engine):
    """training_course_instructors ve training_session_instructors oluşturulmuş olmalı."""
    async with engine.connect() as conn:
        for table in ("training_course_instructors", "training_session_instructors"):
            r = await conn.execute(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = :t)"
            ), {"t": table})
            assert r.scalar(), f"Tablo eksik: {table}"


@pytest.mark.asyncio
async def test_junction_column_types_are_uuid(engine):
    """Junction tablo id/FK kolonları TEXT değil UUID tipinde olmalı.

    0017'den önce sa.Text() kullanıldı; bu test aynı hatanın tekrarlanmamasını garanti eder.
    """
    checks = [
        ("training_course_instructors", "id"),
        ("training_course_instructors", "club_id"),
        ("training_course_instructors", "course_id"),
        ("training_course_instructors", "person_id"),
        ("training_session_instructors", "id"),
        ("training_session_instructors", "club_id"),
        ("training_session_instructors", "session_id"),
        ("training_session_instructors", "person_id"),
    ]
    async with engine.connect() as conn:
        for table, col in checks:
            r = await conn.execute(text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
            ), {"t": table, "c": col})
            row = r.fetchone()
            assert row is not None, f"Kolon bulunamadı: {table}.{col}"
            assert row[0] == "uuid", (
                f"Tip hatası: {table}.{col} = {row[0]!r}, beklenen 'uuid'. "
                f"Migration'da sa.UUID() yerine sa.Text() kullanılmış."
            )


@pytest.mark.asyncio
async def test_unique_constraints_exist(engine):
    """Unique constraint'ler doğru tanımlanmış olmalı."""
    async with engine.connect() as conn:
        for table, constraint in (
            ("training_course_instructors", "uq_tci_course_person"),
            ("training_session_instructors", "uq_tsi_session_person"),
        ):
            r = await conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.table_constraints "
                "WHERE table_schema = 'public' AND table_name = :t "
                "  AND constraint_name = :c AND constraint_type = 'UNIQUE'"
            ), {"t": table, "c": constraint})
            assert r.scalar() == 1, f"Unique constraint eksik: {constraint} on {table}"


@pytest.mark.asyncio
async def test_fk_constraints_exist(engine):
    """Junction tablolardaki FK'lar doğru referans tablolarına bağlı olmalı."""
    expected = [
        ("training_course_instructors", "clubs"),
        ("training_course_instructors", "training_courses"),
        ("training_course_instructors", "persons"),
        ("training_session_instructors", "clubs"),
        ("training_session_instructors", "training_sessions"),
        ("training_session_instructors", "persons"),
    ]
    async with engine.connect() as conn:
        for src_table, ref_table in expected:
            r = await conn.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.referential_constraints rc
                JOIN information_schema.table_constraints src
                  ON src.constraint_name = rc.constraint_name
                 AND src.table_name = :src
                 AND src.table_schema = 'public'
                JOIN information_schema.table_constraints ref
                  ON ref.constraint_name = rc.unique_constraint_name
                 AND ref.table_name = :ref
                 AND ref.table_schema = 'public'
            """), {"src": src_table, "ref": ref_table})
            assert r.scalar() >= 1, f"FK eksik: {src_table} → {ref_table}"


# ── 3. Veri migrasyonu (0016 → 0017) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_data_migration_instructor_to_junction(engine):
    """0016 state'indeki instructor_person_id verisi 0017'de junction tabloya taşınmalı.

    Adımlar:
      1. 0016'ya downgrade (junction tablolar yok)
      2. Test verisi ekle: club + person + training_course(instructor_person_id dolu)
      3. head'e upgrade (0017 — veri migrasyonu çalışır)
      4. training_course_instructors'da kayıt olduğunu doğrula
      5. CASCADE ile temizlik
    """
    club_id = uuid.uuid4()
    person_id = uuid.uuid4()
    course_id = uuid.uuid4()

    # 1. Downgrade → 0016
    run_alembic("downgrade", "0016")

    # 2. Minimal test verisi (0016 state: junction tablolar yok, instructor_person_id mevcut)
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO clubs (id, slug, name, plan, is_active)
            VALUES (:id, :slug, 'PG Migration Test Kulübü', 'starter', true)
        """), {"id": club_id, "slug": f"pg-mig-{club_id.hex[:8]}"})

        await conn.execute(text("""
            INSERT INTO persons (id, club_id, first_name, last_name)
            VALUES (:id, :club_id, 'Test', 'Antrenör')
        """), {"id": person_id, "club_id": club_id})

        await conn.execute(text("""
            INSERT INTO training_courses (id, club_id, name, instructor_person_id)
            VALUES (:id, :club_id, 'PG Migration Test Kursu', :person_id)
        """), {"id": course_id, "club_id": club_id, "person_id": person_id})

    # 3. Upgrade → head (0017, veri migrasyonu çalışır)
    run_alembic("upgrade", "head")

    # 4. Doğrula
    async with engine.connect() as conn:
        r = await conn.execute(text("""
            SELECT COUNT(*) FROM training_course_instructors
            WHERE course_id = :course_id AND person_id = :person_id
        """), {"course_id": course_id, "person_id": person_id})
        count = r.scalar()

    # 5. Temizlik (clubs CASCADE ile alt kayıtları siler)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM clubs WHERE id = :id"), {"id": club_id})

    assert count == 1, (
        f"Veri migrasyonu başarısız: training_course_instructors'da kayıt bulunamadı "
        f"(course_id={course_id}, person_id={person_id}). "
        f"Migration 0017 upgrade() içindeki veri kopyalama bloğunu kontrol edin."
    )


# ── 4. Migration 0017 → 0018: attendance_mode ────────────────────────────────

@pytest.mark.asyncio
async def test_0018_attendance_mode_column_exists(engine):
    """0018 migration sonrası training_courses.attendance_mode kolonu var olmalı."""
    async with engine.connect() as conn:
        r = await conn.execute(text("""
            SELECT column_name, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'training_courses'
              AND column_name = 'attendance_mode'
        """))
        row = r.fetchone()
    assert row is not None, "training_courses.attendance_mode kolonu bulunamadı (0018 migration çalışmadı?)"
    assert row[2] == "NO", "attendance_mode nullable olmamalı"
    assert "coach_daily" in (row[1] or ""), f"Varsayılan değer 'coach_daily' olmalı, alınan: {row[1]!r}"


@pytest.mark.asyncio
async def test_0018_attendance_mode_enum_type_exists(engine):
    """PostgreSQL'de 'attendancemodeenum' tip tanımlı olmalı."""
    async with engine.connect() as conn:
        r = await conn.execute(text("""
            SELECT typname FROM pg_type WHERE typname = 'attendancemodeenum'
        """))
        row = r.fetchone()
    assert row is not None, "attendancemodeenum enum tipi bulunamadı"


@pytest.mark.asyncio
async def test_0018_downgrade_removes_column(engine):
    """0018 downgrade → attendance_mode kolonu ve enum tipi kaldırılmalı."""
    run_alembic("downgrade", "0017")
    try:
        async with engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'training_courses'
                  AND column_name = 'attendance_mode'
            """))
            row = r.fetchone()
        assert row is None, "Downgrade sonrası attendance_mode kolonu hâlâ var"

        async with engine.connect() as conn:
            r2 = await conn.execute(text("""
                SELECT typname FROM pg_type WHERE typname = 'attendancemodeenum'
            """))
            row2 = r2.fetchone()
        assert row2 is None, "Downgrade sonrası attendancemodeenum tipi hâlâ var"
    finally:
        # Testler için head'e geri dön
        run_alembic("upgrade", "head")


# ── 5. Migration 0021: program_preference ────────────────────────────────────

@pytest.mark.asyncio
async def test_0021_column_exists_and_nullable(engine):
    """0021 sonrası membership_applications.program_preference kolonu nullable VARCHAR(50)."""
    async with engine.connect() as conn:
        r = await conn.execute(text("""
            SELECT data_type, character_maximum_length, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name   = 'membership_applications'
              AND column_name  = 'program_preference'
        """))
        row = r.fetchone()
    assert row is not None, "membership_applications.program_preference kolonu bulunamadı"
    assert row[0] in ("character varying", "varchar"), f"Tip yanlış: {row[0]!r}"
    assert row[1] == 50, f"Uzunluk 50 olmalı, alınan: {row[1]!r}"
    assert row[2] == "YES", "program_preference nullable olmalı"


@pytest.mark.asyncio
async def test_0021_check_constraint_exists(engine):
    """CHECK constraint ck_membership_applications_program_preference tanımlı olmalı."""
    async with engine.connect() as conn:
        r = await conn.execute(text("""
            SELECT COUNT(*) FROM information_schema.table_constraints
            WHERE table_schema    = 'public'
              AND table_name      = 'membership_applications'
              AND constraint_name = 'ck_membership_applications_program_preference'
              AND constraint_type = 'CHECK'
        """))
        count = r.scalar()
    assert count == 1, "CHECK constraint bulunamadı"


@pytest.mark.asyncio
async def test_0021_check_constraint_rejects_invalid_value(engine):
    """DB CHECK constraint geçersiz program_preference değerini reddetmeli."""
    import sqlalchemy.exc
    import uuid as _uuid
    club_id = _uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO clubs (id, slug, name, plan, is_active)
            VALUES (:id, :slug, 'CHECK Test Kulübü', 'starter', true)
        """), {"id": club_id, "slug": f"chk-{club_id.hex[:8]}"})

    try:
        # pytest.raises engine.begin() dışında sarmalıyor —
        # IntegrityError transaction'dan çıkınca yakalanır, rollback doğal yapılır.
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(text("""
                    INSERT INTO membership_applications
                      (id, club_id, status, program_preference)
                    VALUES (:id, :club_id, 'submitted', 'gecersiz_deger')
                """), {"id": _uuid.uuid4(), "club_id": club_id})
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM clubs WHERE id = :id"), {"id": club_id})


@pytest.mark.asyncio
async def test_0021_check_constraint_accepts_valid_values(engine):
    """CHECK constraint geçerli program_preference değerlerini kabul etmeli."""
    import uuid as _uuid
    club_id = _uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO clubs (id, slug, name, plan, is_active)
            VALUES (:id, :slug, 'Valid Check Test', 'starter', true)
        """), {"id": club_id, "slug": f"vld-{club_id.hex[:8]}"})

    try:
        async with engine.begin() as conn:
            for val in ("optimist", "ilca", "420", "wing_foil", "para_yelken", None):
                await conn.execute(text("""
                    INSERT INTO membership_applications
                      (id, club_id, status, program_preference)
                    VALUES (:id, :club_id, 'submitted', :pp)
                """), {"id": _uuid.uuid4(), "club_id": club_id, "pp": val})
    finally:
        # FK sırası: önce membership_applications, sonra clubs
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM membership_applications WHERE club_id = :id"),
                {"id": club_id},
            )
            await conn.execute(text("DELETE FROM clubs WHERE id = :id"), {"id": club_id})


def test_0021_roundtrip_downgrade_upgrade():
    """0020'ye downgrade → 0021'e tekrar upgrade: revision + kolon + CHECK doğrulanır."""
    try:
        run_alembic("downgrade", "0020")
        run_alembic("upgrade", "0021")

        async def _check() -> None:
            e = create_async_engine(DATABASE_URL, echo=False)
            try:
                async with e.connect() as conn:
                    r = await conn.execute(text("SELECT version_num FROM alembic_version"))
                    assert r.scalar_one() == "0021", "Roundtrip sonrası revision 0021 değil"

                    r2 = await conn.execute(text("""
                        SELECT COUNT(*) FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name   = 'membership_applications'
                          AND column_name  = 'program_preference'
                    """))
                    assert r2.scalar() == 1, "Roundtrip sonrası program_preference kolonu yok"

                    r3 = await conn.execute(text("""
                        SELECT COUNT(*) FROM information_schema.table_constraints
                        WHERE table_schema    = 'public'
                          AND table_name      = 'membership_applications'
                          AND constraint_name = 'ck_membership_applications_program_preference'
                          AND constraint_type = 'CHECK'
                    """))
                    assert r3.scalar() == 1, "Roundtrip sonrası CHECK constraint yok"
            finally:
                await e.dispose()

        asyncio.get_event_loop().run_until_complete(_check())
    finally:
        # Assertion veya upgrade hatası olsa bile head'e dön
        run_alembic("upgrade", "head")


def test_0021_downgrade_removes_column_and_constraint():
    """0021 downgrade: CHECK constraint ve kolon kaldırılmalı."""
    run_alembic("downgrade", "0020")
    try:
        import asyncio
        async def _check():
            e = create_async_engine(DATABASE_URL, echo=False)
            async with e.connect() as conn:
                # Kolon gitmiş olmalı
                r = await conn.execute(text("""
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name   = 'membership_applications'
                      AND column_name  = 'program_preference'
                """))
                assert r.scalar() == 0, "Downgrade sonrası program_preference kolonu hâlâ var"
                # Constraint gitmiş olmalı
                r2 = await conn.execute(text("""
                    SELECT COUNT(*) FROM information_schema.table_constraints
                    WHERE table_schema    = 'public'
                      AND table_name      = 'membership_applications'
                      AND constraint_name = 'ck_membership_applications_program_preference'
                """))
                assert r2.scalar() == 0, "Downgrade sonrası CHECK constraint hâlâ var"
            await e.dispose()
        asyncio.get_event_loop().run_until_complete(_check())
    finally:
        run_alembic("upgrade", "head")


# ── 6. Migration 0022: preferred_course_id ───────────────────────────────────

@pytest.mark.asyncio
async def test_0022_column_exists_and_nullable(engine):
    """0022 sonrası membership_applications.preferred_course_id kolonu nullable UUID."""
    async with engine.connect() as conn:
        r = await conn.execute(text("""
            SELECT data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name   = 'membership_applications'
              AND column_name  = 'preferred_course_id'
        """))
        row = r.fetchone()
    assert row is not None, "membership_applications.preferred_course_id kolonu bulunamadı"
    assert row[0] == "uuid", f"Tip UUID olmalı, alınan: {row[0]!r}"
    assert row[1] == "YES", "preferred_course_id nullable olmalı"


@pytest.mark.asyncio
async def test_0022_fk_to_training_courses(engine):
    """preferred_course_id → training_courses.id FK tanımlı olmalı."""
    async with engine.connect() as conn:
        r = await conn.execute(text("""
            SELECT COUNT(*)
            FROM information_schema.referential_constraints rc
            JOIN information_schema.table_constraints src
              ON src.constraint_name = rc.constraint_name
             AND src.table_name = 'membership_applications'
             AND src.table_schema = 'public'
            JOIN information_schema.table_constraints ref
              ON ref.constraint_name = rc.unique_constraint_name
             AND ref.table_name = 'training_courses'
             AND ref.table_schema = 'public'
        """))
        count = r.scalar()
    assert count >= 1, "preferred_course_id → training_courses FK bulunamadı"


@pytest.mark.asyncio
async def test_0022_composite_index_exists(engine):
    """(club_id, preferred_course_id) composite index tanımlı olmalı."""
    async with engine.connect() as conn:
        r = await conn.execute(text("""
            SELECT COUNT(*) FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename  = 'membership_applications'
              AND indexname  = 'ix_membership_applications_club_preferred_course'
        """))
        count = r.scalar()
    assert count == 1, "ix_membership_applications_club_preferred_course index bulunamadı"


@pytest.mark.asyncio
async def test_0022_null_accepted(engine):
    """preferred_course_id=NULL başarıyla eklenmeli."""
    import uuid as _uuid
    club_id = _uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO clubs (id, slug, name, plan, is_active)
            VALUES (:id, :slug, '0022 NULL Test', 'starter', true)
        """), {"id": club_id, "slug": f"null22-{club_id.hex[:8]}"})
    try:
        async with engine.begin() as conn:
            app_id = _uuid.uuid4()
            await conn.execute(text("""
                INSERT INTO membership_applications (id, club_id, status, preferred_course_id)
                VALUES (:id, :club_id, 'submitted', NULL)
            """), {"id": app_id, "club_id": club_id})
        async with engine.connect() as conn:
            r = await conn.execute(text(
                "SELECT preferred_course_id FROM membership_applications WHERE id = :id"
            ), {"id": app_id})
            assert r.scalar() is None, "preferred_course_id NULL olmalı"
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM membership_applications WHERE club_id = :id"), {"id": club_id})
            await conn.execute(text("DELETE FROM clubs WHERE id = :id"), {"id": club_id})


def test_0022_downgrade_removes_column_index_fk():
    """0022 downgrade: kolon, index ve FK kaldırılmalı."""
    try:
        run_alembic("downgrade", "0021")

        async def _check() -> None:
            e = create_async_engine(DATABASE_URL, echo=False)
            try:
                async with e.connect() as conn:
                    r = await conn.execute(text("""
                        SELECT COUNT(*) FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name   = 'membership_applications'
                          AND column_name  = 'preferred_course_id'
                    """))
                    assert r.scalar() == 0, "Downgrade sonrası preferred_course_id kolonu hâlâ var"

                    r2 = await conn.execute(text("""
                        SELECT COUNT(*) FROM pg_indexes
                        WHERE schemaname = 'public'
                          AND tablename  = 'membership_applications'
                          AND indexname  = 'ix_membership_applications_club_preferred_course'
                    """))
                    assert r2.scalar() == 0, "Downgrade sonrası composite index hâlâ var"
            finally:
                await e.dispose()

        asyncio.get_event_loop().run_until_complete(_check())
    finally:
        run_alembic("upgrade", "head")


# ── 8. Downgrade/upgrade döngüsü ─────────────────────────────────────────────

def test_downgrade_then_upgrade_idempotent():
    """Downgrade 0016 → upgrade head tekrar sorunsuz çalışmalı (idempotency)."""
    run_alembic("downgrade", "0016")
    run_alembic("upgrade", "head")
