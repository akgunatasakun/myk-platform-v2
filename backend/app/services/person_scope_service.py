"""Kendi kaydı / aktif veli ilişkisi için tenant sınırlandırılmış okuma kapsamı."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.person_guardian import PersonGuardian
from app.models.user import User


async def get_own_person_ids(
    user_id: uuid.UUID, club_id: uuid.UUID, db: AsyncSession, role: str
) -> list[uuid.UUID]:
    person_id = (
        await db.execute(
            select(User.person_id).where(
                User.id == user_id,
                User.club_id == club_id,
                User.is_active.is_(True),
                User.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if person_id is None:
        return []
    if role == "sporcu":
        return [person_id]
    if role == "veli":
        return list(
            (
                await db.execute(
                    select(PersonGuardian.athlete_person_id).where(
                        PersonGuardian.club_id == club_id,
                        PersonGuardian.guardian_person_id == person_id,
                        PersonGuardian.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
    return []
