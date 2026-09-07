#!/usr/bin/env python3
"""UAT: Test antrenör Person + User kaydı oluşturur.

Kullanım (sunucuda):
  cd /opt/myk/production/myk-platform-v2
  PDC="docker compose -p myk-production --env-file /etc/myk/production.env \
    -f docker-compose.yml -f docker-compose.prod.yml"
  $PDC exec api python scripts/create_test_antrenor.py

Oluşturduğu kayıtları sona kadar yazar; geçici parolayı ekrana basar.
Test bitince aynı scripti --delete ile çalıştırıp temizleyin.
"""
from __future__ import annotations
import asyncio
import sys
import uuid
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(_REPO))

CLUB_ID = uuid.UUID("c145c694-0934-45bc-b316-dcc0c4f3aa82")
TEST_EMAIL = "test.antrenor@myk-uat.local"
TEST_NAME_FIRST = "Test"
TEST_NAME_LAST = "Antrenör"

import secrets

async def main() -> None:
    from app.database import AsyncSessionLocal
    from app.models.person import Person, PersonRole
    from app.models.user import User
    from app.core.security import hash_password
    from sqlalchemy import select, delete

    delete_mode = "--delete" in sys.argv

    async with AsyncSessionLocal() as db:
        # Mevcut kaydı kontrol et
        existing = (await db.execute(
            select(User).where(User.email == TEST_EMAIL)
        )).scalar_one_or_none()

        if delete_mode:
            if existing:
                if existing.person_id:
                    await db.execute(delete(Person).where(Person.id == existing.person_id))
                await db.execute(delete(User).where(User.id == existing.id))
                await db.commit()
                print(f"✓ Test antrenör silindi: {TEST_EMAIL}")
            else:
                print("Kayıt bulunamadı, silinecek bir şey yok.")
            return

        if existing:
            print(f"⚠ Test antrenör zaten mevcut: {TEST_EMAIL}")
            print("  Silmek için: python scripts/create_test_antrenor.py --delete")
            return

        # 1. Person oluştur
        person = Person(
            club_id=CLUB_ID,
            first_name=TEST_NAME_FIRST,
            last_name=TEST_NAME_LAST,
            email=TEST_EMAIL,
            is_active=True,
        )
        db.add(person)
        await db.flush()  # person.id alınır

        # 2. PersonRole: antrenor
        pr = PersonRole(person_id=person.id, role_code="antrenor")
        db.add(pr)

        # 3. User oluştur
        temp_pw = secrets.token_urlsafe(12)
        user = User(
            club_id=CLUB_ID,
            email=TEST_EMAIL,
            password_hash=hash_password(temp_pw),
            full_name=f"{TEST_NAME_FIRST} {TEST_NAME_LAST}",
            role="antrenor",
            is_active=True,
            person_id=person.id,
            must_change_password=False,
        )
        db.add(user)
        await db.commit()

        print()
        print("=== Test Antrenör Oluşturuldu ===")
        print(f"  E-posta : {TEST_EMAIL}")
        print(f"  Parola  : {temp_pw}")
        print(f"  Person  : {person.id}")
        print(f"  User    : {user.id}")
        print()
        print("Testi bitirince silin:")
        print("  python scripts/create_test_antrenor.py --delete")
        print()

asyncio.run(main())
