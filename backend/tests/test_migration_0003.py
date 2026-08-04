"""Migration 0003 şema doğrulama testleri — MG-01 .. MG-05.

Bu testler SQLite in-memory veritabanı üzerinde modelin ORM tarafını doğrular.
Gerçek Alembic upgrade/downgrade döngüsü Docker+PostgreSQL ortamında
sprint_3_2_verify.sh ile test edilir.
"""
import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.club import Club
from app.models.person import Person
from app.models.sports_branch import SportsBranch
from app.models.membership_application import MembershipApplication


# ── MG-01: Person.avatar_object_key var, avatar_url yok ───────────────────

def test_mg01_person_has_avatar_object_key() -> None:
    """Person modelinde avatar_object_key kolonu var, avatar_url yok."""
    columns = {col.key for col in Person.__table__.columns}
    assert "avatar_object_key" in columns, "avatar_object_key kolonu eksik"
    assert "avatar_url" not in columns, "avatar_url kolonu hâlâ var — migration uygulanmamış"


# ── MG-02: SportsBranch tablosu tanımlı ───────────────────────────────────

def test_mg02_sports_branches_table_defined() -> None:
    """SportsBranch tablosu ORM'de tanımlı ve gerekli kolonları içeriyor."""
    columns = {col.key for col in SportsBranch.__table__.columns}
    for expected in ("id", "club_id", "name", "is_active", "sort_order", "created_at"):
        assert expected in columns, f"Beklenen kolon eksik: {expected}"


# ── MG-03: MembershipApplication tablosu tanımlı ─────────────────────────

def test_mg03_membership_application_table_defined() -> None:
    """MembershipApplication tablosu ORM'de tanımlı ve tüm kolonları içeriyor."""
    columns = {col.key for col in MembershipApplication.__table__.columns}
    required = (
        "id", "club_id", "person_id", "applicant_name", "status",
        "form_data", "pdf_object_key", "pdf_sha256",
        "signature_object_key", "signature_sha256",
        "signed_at", "signed_by_user_id", "approved_by_user_id", "approved_at",
        "created_at", "updated_at",
    )
    for col in required:
        assert col in columns, f"Beklenen kolon eksik: {col}"


# ── MG-04: SQLite'ta model örnekleri oluşturulabilir ──────────────────────

@pytest.mark.asyncio
async def test_mg04_create_sports_branch(
    db_session: AsyncSession, test_club: Club
) -> None:
    """SQLite test DB'de SportsBranch kaydı oluşturulabilir."""
    branch = SportsBranch(
        id=uuid.uuid4(),
        club_id=test_club.id,
        name="Yelken",
        is_active=True,
        sort_order=0,
    )
    db_session.add(branch)
    await db_session.flush()

    assert branch.id is not None
    assert branch.club_id == test_club.id
    assert branch.name == "Yelken"


@pytest.mark.asyncio
async def test_mg05_create_membership_application(
    db_session: AsyncSession, test_club: Club
) -> None:
    """SQLite test DB'de MembershipApplication kaydı oluşturulabilir."""
    # Önce bir person gerekiyor
    person = Person(
        id=uuid.uuid4(),
        club_id=test_club.id,
        first_name="Ali",
        last_name="Veli",
        is_active=True,
        is_deleted=False,
    )
    db_session.add(person)
    await db_session.flush()

    app = MembershipApplication(
        id=uuid.uuid4(),
        club_id=test_club.id,
        person_id=person.id,
        applicant_name="Ali Veli",
        status="draft",
        form_data={"branch": "Yelken"},
    )
    db_session.add(app)
    await db_session.flush()

    assert app.id is not None
    assert app.status == "draft"
    assert app.signature_sha256 is None


@pytest.mark.asyncio
async def test_mg06_person_avatar_object_key_nullable(
    db_session: AsyncSession, test_club: Club
) -> None:
    """Person kaydı avatar_object_key olmadan oluşturulabilir (nullable)."""
    person = Person(
        id=uuid.uuid4(),
        club_id=test_club.id,
        first_name="Zeynep",
        last_name="Kaya",
        is_active=True,
        is_deleted=False,
        avatar_object_key=None,
    )
    db_session.add(person)
    await db_session.flush()

    assert person.avatar_object_key is None


@pytest.mark.asyncio
async def test_mg07_unique_branch_name_per_club(
    db_session: AsyncSession, test_club: Club
) -> None:
    """Aynı kulüpte aynı branş adını iki kez eklemek IntegrityError atar."""
    from sqlalchemy.exc import IntegrityError

    branch1 = SportsBranch(
        id=uuid.uuid4(),
        club_id=test_club.id,
        name="Optimist",
        sort_order=1,
    )
    branch2 = SportsBranch(
        id=uuid.uuid4(),
        club_id=test_club.id,
        name="Optimist",  # aynı ad — UNIQUE constraint ihlali
        sort_order=2,
    )
    db_session.add(branch1)
    await db_session.flush()

    db_session.add(branch2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
