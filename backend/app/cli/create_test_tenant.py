"""
Test ortamı için kulüp + yönetici oluşturma CLI komutu.

SADECE development / test ortamında çalışır.
Production'da (MYK_ENV=production) reddeder.

Kullanım (Docker container içinde):
    docker compose exec api python -m app.cli.create_test_tenant \\
        --name "İkinci Kulüp" \\
        --slug "ikinci-kulup" \\
        --admin-email "admin2@ikinci.com" \\
        [--admin-password "Test1234!"]

Çıktı:
    ✅ Kulüp oluşturuldu: İkinci Kulüp (slug=ikinci-kulup)
    ✅ Yönetici oluşturuldu: admin2@ikinci.com
       club_id: <uuid>
       user_id: <uuid>
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import select

from app.config import get_settings
from app.core.security import hash_password
from app.database import AsyncSessionLocal
from app.models.club import Club
from app.models.user import User

_ALLOWED_ENVS = {"development", "test"}


async def _create_tenant(
    name: str,
    slug: str,
    admin_email: str,
    admin_password: str,
) -> None:
    settings = get_settings()

    if settings.myk_env not in _ALLOWED_ENVS:
        print(
            f"ERROR: Bu komut yalnızca {_ALLOWED_ENVS} ortamında çalışır. "
            f"Mevcut ortam: {settings.myk_env!r}",
            file=sys.stderr,
        )
        sys.exit(1)

    async with AsyncSessionLocal() as session:
        # Slug çakışması kontrolü
        result = await session.execute(select(Club).where(Club.slug == slug))
        if result.scalar_one_or_none() is not None:
            print(f"ERROR: '{slug}' slug zaten kullanımda.", file=sys.stderr)
            sys.exit(2)

        # Kulüp oluştur
        club = Club(
            id=uuid.uuid4(),
            slug=slug,
            name=name,
            plan="starter",
            is_active=True,
            settings={},
        )
        session.add(club)

        # Yönetici kullanıcı oluştur
        user = User(
            id=uuid.uuid4(),
            club_id=club.id,
            email=admin_email,
            password_hash=hash_password(admin_password),
            full_name=f"{name} Yöneticisi",
            role="kulup_yonetici",
            is_active=True,
            is_deleted=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(club)
        await session.refresh(user)

    print(f"✅ Kulüp oluşturuldu: {name} (slug={slug})")
    print(f"✅ Yönetici oluşturuldu: {admin_email}")
    print(f"   club_id: {club.id}")
    print(f"   user_id: {user.id}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test ortamı için kulüp + yönetici oluştur (dev/test ONLY)"
    )
    parser.add_argument("--name", required=True, help="Kulüp adı")
    parser.add_argument("--slug", required=True, help="Kulüp slug (URL-friendly)")
    parser.add_argument("--admin-email", required=True, help="Yönetici e-posta")
    parser.add_argument(
        "--admin-password",
        default="Test1234!",
        help="Yönetici parolası (varsayılan: Test1234!)",
    )
    args = parser.parse_args()

    asyncio.run(
        _create_tenant(
            name=args.name,
            slug=args.slug,
            admin_email=args.admin_email,
            admin_password=args.admin_password,
        )
    )


if __name__ == "__main__":
    main()
