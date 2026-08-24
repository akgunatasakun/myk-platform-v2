"""Antrenör kapsam servisi — eğitim scope helper'ları.

Kullanım:
    from app.services.training_scope_service import (
        get_antrenor_course_ids,
        get_antrenor_enrolled_person_ids,
    )

Kurallar:
  - User.person_id bağlantısı olmayan antrenör → HTTP 403
  - Kurs listesi: training_course_instructors UNION session_instructors→course_id UNION legacy
  - Kişi listesi: atandığı kurslara active kayıtlı kişiler + kendi person_id
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training import (
    TrainingCourse,
    TrainingCourseInstructor,
    TrainingEnrollment,
    TrainingSession,
    TrainingSessionInstructor,
)
from app.models.user import User


async def _get_antrenor_person_id(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> uuid.UUID:
    """Antrenörün person_id'sini döndür; bağlantı yoksa 403."""
    result = await db.execute(select(User.person_id).where(User.id == user_id))
    person_id = result.scalar_one_or_none()
    if not person_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kullanıcı hesabı bir kişi kaydına bağlı değil. Lütfen yöneticinize başvurun.",
        )
    return person_id


async def get_antrenor_course_ids(
    user_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
) -> list[uuid.UUID]:
    """Antrenörün erişebileceği kurs UUID listesi.

    Kaynaklar (UNION):
    1. training_course_instructors üzerinden atandığı kurslar
    2. training_session_instructors üzerinden atandığı oturumların kursları
    3. Legacy TrainingCourse.instructor_person_id (geçiş dönemi)
    """
    person_id = await _get_antrenor_person_id(user_id, db)

    course_ids: set[uuid.UUID] = set()

    # 1. Kurs düzeyi atamalar
    r1 = await db.execute(
        select(TrainingCourseInstructor.course_id).where(
            TrainingCourseInstructor.person_id == person_id,
            TrainingCourseInstructor.club_id == club_id,
        )
    )
    course_ids.update(r1.scalars().all())

    # 2. Oturum düzeyi atamalar → kurs_id
    r2 = await db.execute(
        select(TrainingSession.course_id)
        .join(
            TrainingSessionInstructor,
            TrainingSessionInstructor.session_id == TrainingSession.id,
        )
        .where(
            TrainingSessionInstructor.person_id == person_id,
            TrainingSessionInstructor.club_id == club_id,
        )
        .distinct()
    )
    course_ids.update(r2.scalars().all())

    # 3. Legacy instructor_person_id sütunu (geçiş dönemi güvencesi)
    r3 = await db.execute(
        select(TrainingCourse.id).where(
            TrainingCourse.instructor_person_id == person_id,
            TrainingCourse.club_id == club_id,
            TrainingCourse.is_deleted.is_(False),
        )
    )
    course_ids.update(r3.scalars().all())

    return list(course_ids)


async def get_antrenor_enrolled_person_ids(
    user_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
) -> list[uuid.UUID]:
    """Antrenörün erişebileceği kişi UUID listesi.

    = Atandığı kurslara active kayıtlı kişiler + antrenörün kendi person_id'si.
    """
    person_id = await _get_antrenor_person_id(user_id, db)

    course_ids = await get_antrenor_course_ids(user_id, club_id, db)

    ids: set[uuid.UUID] = {person_id}  # kendi kaydı her zaman görünür

    if course_ids:
        r = await db.execute(
            select(TrainingEnrollment.person_id)
            .where(
                TrainingEnrollment.course_id.in_(course_ids),
                TrainingEnrollment.club_id == club_id,
                TrainingEnrollment.status == "active",
                TrainingEnrollment.is_deleted.is_(False),
            )
            .distinct()
        )
        ids.update(r.scalars().all())

    return list(ids)
