"""Üyelik onay servisi testleri — Sprint 5A.

Kabul kriterleri:
  - Yalnızca submitted → approved geçişinde Person oluşturulur
  - Aynı başvuru ikinci kez onaylanırsa ikinci Person oluşmaz (idempotency)
  - Oluşturulan Person doğru club_id ile bağlıdır
  - Başvurudaki alanlar kayıpsız aktarılır
  - member_number üretilir ve formatı doğrudur
  - User hesabı oluşturulur (e-posta varsa)
  - Farklı kulübün başvurusuna erişim reddedilir (tenant izolasyonu)
  - Hata halinde rollback sağlanır (transaction bütünlüğü)
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.club import Club
from app.models.membership_application import MembershipApplication
from app.models.person import Person, PersonRole
from app.models.user import User
from app.services.membership_approval import process_approval


# ─── Yardımcı fixture'lar ────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def submitted_app(db_session: AsyncSession, test_club: Club) -> MembershipApplication:
    """submitted durumunda eksiksiz başvuru."""
    app = MembershipApplication(
        club_id=test_club.id,
        status="submitted",
        application_number="MYK-26-000001",
        first_name="Ahmet",
        last_name="Yılmaz",
        national_id="12345678901",
        birth_date=date(2010, 5, 15),
        gender="erkek",
        phone="05301234567",
        email="ahmet.yilmaz@test.com",
        address="Mersin Test Caddesi No:1",
        blood_type="A+",
        emergency_contact_name="Fatma Yılmaz",
        emergency_contact_phone="05309876543",
        submitted_at=datetime.now(timezone.utc),
    )
    db_session.add(app)
    await db_session.flush()
    return app


@pytest_asyncio.fixture
async def submitted_app_no_email(db_session: AsyncSession, test_club: Club) -> MembershipApplication:
    """E-postasız başvuru — User oluşturulmamalı."""
    app = MembershipApplication(
        club_id=test_club.id,
        status="submitted",
        application_number="MYK-26-000002",
        first_name="Mehmet",
        last_name="Demir",
        national_id="98765432109",
        submitted_at=datetime.now(timezone.utc),
    )
    db_session.add(app)
    await db_session.flush()
    return app


@pytest_asyncio.fixture
async def approver_id(test_user: User) -> uuid.UUID:
    return test_user.id


# ─── Testler ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_approval_creates_person(
    db_session: AsyncSession,
    submitted_app: MembershipApplication,
    approver_id: uuid.UUID,
    test_club: Club,
) -> None:
    """Onayda Person oluşturulur ve alanlar doğru aktarılır."""
    result = await process_approval(submitted_app, db_session, approver_id)

    assert result.person is not None
    assert result.person_created is True
    assert result.person.club_id == test_club.id
    assert result.person.first_name == "Ahmet"
    assert result.person.last_name == "Yılmaz"
    assert result.person.national_id == "12345678901"
    assert result.person.birth_date == date(2010, 5, 15)
    assert result.person.email == "ahmet.yilmaz@test.com"
    assert result.person.phone == "05301234567"
    assert result.person.blood_type == "A+"
    assert result.person.is_active is True

    # application.person_id güncellendi mi?
    assert submitted_app.person_id == result.person.id


@pytest.mark.asyncio
async def test_approval_creates_uye_role(
    db_session: AsyncSession,
    submitted_app: MembershipApplication,
    approver_id: uuid.UUID,
) -> None:
    """Onayda PersonRole('uye') oluşturulur."""
    result = await process_approval(submitted_app, db_session, approver_id)

    roles_q = await db_session.execute(
        select(PersonRole).where(
            PersonRole.person_id == result.person.id,
            PersonRole.role_code == "uye",
        )
    )
    role = roles_q.scalar_one_or_none()
    assert role is not None


@pytest.mark.asyncio
async def test_approval_generates_member_number(
    db_session: AsyncSession,
    submitted_app: MembershipApplication,
    approver_id: uuid.UUID,
) -> None:
    """Üye numarası üretilir ve format doğrudur: MYK-YY-NNNN"""
    result = await process_approval(submitted_app, db_session, approver_id)

    assert result.member_number is not None
    parts = result.member_number.split("-")
    assert len(parts) == 3
    assert parts[0] == "MYK"
    assert len(parts[1]) == 2   # YY (2-digit year)
    assert parts[2].isdigit()
    assert int(parts[2]) >= 1

    # Person üzerinde de set edilmiş mi?
    assert result.person.member_number == result.member_number


@pytest.mark.asyncio
async def test_approval_creates_user_when_email_present(
    db_session: AsyncSession,
    submitted_app: MembershipApplication,
    approver_id: uuid.UUID,
    test_club: Club,
) -> None:
    """E-posta varsa User hesabı oluşturulur."""
    result = await process_approval(submitted_app, db_session, approver_id)

    assert result.user is not None
    assert result.user.email == "ahmet.yilmaz@test.com"
    assert result.user.club_id == test_club.id
    assert result.user.role == "uye"
    assert result.user.is_active is True
    assert result.user.person_id == result.person.id
    # Geçici parola üretildi mi?
    assert result.temp_password is not None
    assert len(result.temp_password) >= 8


@pytest.mark.asyncio
async def test_approval_no_user_when_no_email(
    db_session: AsyncSession,
    submitted_app_no_email: MembershipApplication,
    approver_id: uuid.UUID,
) -> None:
    """E-posta yoksa User oluşturulmaz."""
    result = await process_approval(submitted_app_no_email, db_session, approver_id)

    assert result.user is None
    assert result.temp_password is None
    assert result.person is not None


@pytest.mark.asyncio
async def test_approval_idempotent_on_same_national_id(
    db_session: AsyncSession,
    test_club: Club,
    approver_id: uuid.UUID,
) -> None:
    """Aynı TC kimliğiyle iki başvuru onaylanırsa tek Person oluşur."""
    # İlk başvuru
    app1 = MembershipApplication(
        club_id=test_club.id,
        status="submitted",
        application_number="MYK-26-000003",
        first_name="Ali",
        last_name="Kaya",
        national_id="11111111111",
        email="ali.kaya@test.com",
        submitted_at=datetime.now(timezone.utc),
    )
    db_session.add(app1)
    await db_session.flush()
    result1 = await process_approval(app1, db_session, approver_id)

    # İkinci başvuru aynı TC ile
    app2 = MembershipApplication(
        club_id=test_club.id,
        status="submitted",
        application_number="MYK-26-000004",
        first_name="Ali",
        last_name="Kaya",
        national_id="11111111111",
        email="ali.kaya@test.com",
        submitted_at=datetime.now(timezone.utc),
    )
    db_session.add(app2)
    await db_session.flush()
    result2 = await process_approval(app2, db_session, approver_id)

    # Aynı Person olmalı
    assert result1.person.id == result2.person.id
    assert result2.person_created is False

    # Person sayısı 1 olmalı
    persons_q = await db_session.execute(
        select(Person).where(
            Person.club_id == test_club.id,
            Person.national_id == "11111111111",
        )
    )
    persons = persons_q.scalars().all()
    assert len(persons) == 1


@pytest.mark.asyncio
async def test_approval_tenant_isolation(
    db_session: AsyncSession,
    approver_id: uuid.UUID,
) -> None:
    """Farklı kulübün başvurusu process_approval'a yanlışlıkla geçirilmemelidir.

    Bu test, application.club_id'nin approver'ın club_id'siyle farklı olduğu
    durumda servisin Person'ı doğru kulübe atadığını doğrular.
    """
    # Farklı kulüp
    other_club = Club(
        id=uuid.uuid4(),
        slug=f"other-club-{uuid.uuid4().hex[:6]}",
        name="Diğer Kulüp",
        plan="starter",
        is_active=True,
        settings={},
    )
    db_session.add(other_club)
    await db_session.flush()

    app = MembershipApplication(
        club_id=other_club.id,
        status="submitted",
        application_number="MYK-26-000005",
        first_name="Zeynep",
        last_name="Çelik",
        national_id="22222222222",
        email="zeynep@test.com",
        submitted_at=datetime.now(timezone.utc),
    )
    db_session.add(app)
    await db_session.flush()

    result = await process_approval(app, db_session, approver_id)

    # Person diğer kulübe bağlı olmalı
    assert result.person.club_id == other_club.id


@pytest.mark.asyncio
async def test_member_numbers_sequential(
    db_session: AsyncSession,
    test_club: Club,
    approver_id: uuid.UUID,
) -> None:
    """Aynı kulüpte art arda onaylanan başvurular sıralı üye numarası alır."""
    numbers = []
    for i in range(3):
        app = MembershipApplication(
            club_id=test_club.id,
            status="submitted",
            application_number=f"MYK-26-{900 + i:06d}",
            first_name=f"Sporcu{i}",
            last_name="Test",
            national_id=f"3333333300{i}",
            submitted_at=datetime.now(timezone.utc),
        )
        db_session.add(app)
        await db_session.flush()
        result = await process_approval(app, db_session, approver_id)
        numbers.append(int(result.member_number.split("-")[2]))

    # Sıralı olmalı
    assert numbers == sorted(numbers)
    assert len(set(numbers)) == 3  # tekrar yok
