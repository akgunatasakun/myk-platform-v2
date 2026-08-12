"""Training (Fiziksel Eğitim) API router — kurs, oturum, kayıt, yoklama.

Endpoint listesi:
  GET    /trainings                                         → kurs listesi
  POST   /trainings                                         → kurs oluştur
  GET    /trainings/{course_id}                             → kurs detay
  PATCH  /trainings/{course_id}                             → kurs güncelle
  DELETE /trainings/{course_id}                             → kurs soft-delete

  GET    /trainings/{course_id}/participants                → kayıt listesi
  POST   /trainings/{course_id}/participants                → kayıt ekle
  DELETE /trainings/{course_id}/participants/{person_id}    → kayıt iptal

  GET    /trainings/{course_id}/sessions                    → oturum listesi
  POST   /trainings/{course_id}/sessions                    → oturum oluştur
  PATCH  /trainings/{course_id}/sessions/{session_id}       → oturum güncelle

  GET    /trainings/{course_id}/sessions/{session_id}/attendance  → yoklama listesi
  PUT    /trainings/{course_id}/sessions/{session_id}/attendance  → toplu yoklama (UPSERT)

  GET    /trainings/{course_id}/attendance/report           → devam raporu

Tenant isolation: club_id JWT'den gelir, body'den asla kabul edilmez.
RBAC: egitim:read/write, yoklama:read/write (mevcut RBAC matrisi kullanılır).
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import log_action
from app.core.rbac import require_permission
from app.services.event_service import emit_event
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.person import Person
from app.models.training import (
    TrainingAttendance,
    TrainingCourse,
    TrainingEnrollment,
    TrainingSession,
)
from app.schemas.auth import TokenPayload
from app.schemas.training import (
    AttendanceBulkResult,
    AttendanceBulkUpdate,
    AttendancePersonSummary,
    AttendanceReport,
    TrainingAttendanceOut,
    TrainingCourseCreate,
    TrainingCourseListOut,
    TrainingCourseOut,
    TrainingCourseUpdate,
    TrainingEnrollmentCreate,
    TrainingEnrollmentOut,
    TrainingSessionCreate,
    TrainingSessionOut,
    TrainingSessionUpdate,
)

router = APIRouter(prefix="/trainings", tags=["training"])


# ─── Yardımcı fonksiyonlar ────────────────────────────────────────────────────

async def _get_course(
    course_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
    *,
    include_deleted: bool = False,
) -> TrainingCourse:
    """Kursu club_id ile filtreli yükle; bulunamazsa 404."""
    q = select(TrainingCourse).where(
        TrainingCourse.id == course_id,
        TrainingCourse.club_id == club_id,
    )
    if not include_deleted:
        q = q.where(TrainingCourse.is_deleted.is_(False))
    result = await db.execute(q)
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kurs bulunamadı.")
    return course


async def _get_session(
    session_id: uuid.UUID,
    course_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
) -> TrainingSession:
    """Oturumu course_id ve club_id ile filtreli yükle; bulunamazsa 404."""
    result = await db.execute(
        select(TrainingSession).where(
            TrainingSession.id == session_id,
            TrainingSession.course_id == course_id,
            TrainingSession.club_id == club_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oturum bulunamadı.")
    return session


def _person_name(person: Optional[Person]) -> Optional[str]:
    if person is None:
        return None
    return f"{person.first_name} {person.last_name}"


def _enrollment_count(course: TrainingCourse) -> int:
    """Yüklü enrollments varsa kullan; yoksa 0."""
    return sum(
        1 for e in (course.enrollments or [])
        if e.status == "active" and not e.is_deleted
    )


async def _active_enrollment_count(
    course_id: uuid.UUID, club_id: uuid.UUID, db: AsyncSession
) -> int:
    result = await db.execute(
        select(func.count()).where(
            TrainingEnrollment.course_id == course_id,
            TrainingEnrollment.club_id == club_id,
            TrainingEnrollment.status == "active",
            TrainingEnrollment.is_deleted.is_(False),
        )
    )
    return result.scalar_one()


# ─── Kurslar ──────────────────────────────────────────────────────────────────

@router.get("", response_model=TrainingCourseListOut)
async def list_courses(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    active_only: bool = Query(True),
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("egitim:read")),
    db: AsyncSession = Depends(get_db),
) -> TrainingCourseListOut:
    q = select(TrainingCourse).where(
        TrainingCourse.club_id == club_id,
        TrainingCourse.is_deleted.is_(False),
    )
    if active_only:
        q = q.where(TrainingCourse.is_active.is_(True))
    if status_filter:
        q = q.where(TrainingCourse.status == status_filter)

    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = count_result.scalar_one()

    result = await db.execute(
        q.order_by(TrainingCourse.start_date.desc().nullslast(), TrainingCourse.name)
        .offset(skip)
        .limit(limit)
    )
    courses = result.scalars().all()

    items = []
    for c in courses:
        cnt = await _active_enrollment_count(c.id, club_id, db)
        out = TrainingCourseOut.model_validate(c)
        out.enrollment_count = cnt
        items.append(out)

    return TrainingCourseListOut(items=items, total=total, skip=skip, limit=limit)


@router.post("", response_model=TrainingCourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(
    body: TrainingCourseCreate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("egitim:write")),
    db: AsyncSession = Depends(get_db),
) -> TrainingCourseOut:
    # Eğitmen bu kulübe ait mi?
    if body.instructor_person_id is not None:
        p = await db.execute(
            select(Person).where(
                Person.id == body.instructor_person_id,
                Person.club_id == club_id,
                Person.is_deleted.is_(False),
            )
        )
        if p.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Eğitmen olarak atanacak kişi bu kulüpte bulunamadı.",
            )

    course = TrainingCourse(
        club_id=club_id,
        name=body.name,
        description=body.description,
        class_name=body.class_name,
        level=body.level,
        start_date=body.start_date,
        end_date=body.end_date,
        schedule_text=body.schedule_text,
        capacity=body.capacity,
        fee=body.fee,
        instructor_person_id=body.instructor_person_id,
        status=body.status,
    )
    db.add(course)
    await db.flush()

    await log_action(
        db,
        action="training_course_created",
        resource_type="training_course",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(course.id),
        after={"name": course.name, "status": course.status, "capacity": course.capacity},
        request=request,
    )

    out = TrainingCourseOut.model_validate(course)
    out.enrollment_count = 0
    return out


@router.get("/{course_id}", response_model=TrainingCourseOut)
async def get_course(
    course_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    _: None = Depends(require_permission("egitim:read")),
    db: AsyncSession = Depends(get_db),
) -> TrainingCourseOut:
    course = await _get_course(course_id, club_id, db)
    cnt = await _active_enrollment_count(course_id, club_id, db)
    out = TrainingCourseOut.model_validate(course)
    out.enrollment_count = cnt
    return out


@router.patch("/{course_id}", response_model=TrainingCourseOut)
async def update_course(
    course_id: uuid.UUID,
    body: TrainingCourseUpdate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("egitim:write")),
    db: AsyncSession = Depends(get_db),
) -> TrainingCourseOut:
    course = await _get_course(course_id, club_id, db)
    update_data = body.model_dump(exclude_unset=True)

    if not update_data:
        cnt = await _active_enrollment_count(course_id, club_id, db)
        out = TrainingCourseOut.model_validate(course)
        out.enrollment_count = cnt
        return out

    # Eğitmen değişiyorsa bu kulüpte var mı kontrol et
    new_instructor_id = update_data.get("instructor_person_id")
    if new_instructor_id is not None:
        p = await db.execute(
            select(Person).where(
                Person.id == new_instructor_id,
                Person.club_id == club_id,
                Person.is_deleted.is_(False),
            )
        )
        if p.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Eğitmen olarak atanacak kişi bu kulüpte bulunamadı.",
            )

    before = {k: str(getattr(course, k)) for k in update_data if hasattr(course, k)}
    for field, value in update_data.items():
        setattr(course, field, value)
    await db.flush()
    # PostgreSQL onupdate=func.now() ile üretilen updated_at gibi
    # server-side alanları AsyncSession içinde güvenli şekilde yeniden yükle.
    await db.refresh(course)

    await log_action(
        db,
        action="training_course_updated",
        resource_type="training_course",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(course.id),
        before=before,
        after={k: str(v) for k, v in update_data.items()},
        request=request,
    )

    cnt = await _active_enrollment_count(course_id, club_id, db)
    out = TrainingCourseOut.model_validate(course)
    out.enrollment_count = cnt
    return out


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: uuid.UUID,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("egitim:write")),
    db: AsyncSession = Depends(get_db),
) -> None:
    course = await _get_course(course_id, club_id, db)
    course.is_deleted = True
    course.is_active = False
    await db.flush()

    await log_action(
        db,
        action="training_course_deleted",
        resource_type="training_course",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(course.id),
        request=request,
    )


# ─── Katılımcılar (Enrollments) ───────────────────────────────────────────────

@router.get("/{course_id}/participants", response_model=List[TrainingEnrollmentOut])
async def list_participants(
    course_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    _: None = Depends(require_permission("egitim:read")),
    db: AsyncSession = Depends(get_db),
) -> List[TrainingEnrollmentOut]:
    await _get_course(course_id, club_id, db)

    result = await db.execute(
        select(TrainingEnrollment)
        .options(selectinload(TrainingEnrollment.person))
        .where(
            TrainingEnrollment.course_id == course_id,
            TrainingEnrollment.club_id == club_id,
            TrainingEnrollment.is_deleted.is_(False),
        )
        .order_by(TrainingEnrollment.enrolled_at)
    )
    enrollments = result.scalars().all()

    items = []
    for e in enrollments:
        out = TrainingEnrollmentOut.model_validate(e)
        out.person_name = _person_name(e.person)
        items.append(out)
    return items


@router.post(
    "/{course_id}/participants",
    response_model=TrainingEnrollmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_participant(
    course_id: uuid.UUID,
    body: TrainingEnrollmentCreate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("egitim:write")),
    db: AsyncSession = Depends(get_db),
) -> TrainingEnrollmentOut:
    course = await _get_course(course_id, club_id, db)

    # Kişi bu kulüpte var mı?
    person_result = await db.execute(
        select(Person).where(
            Person.id == body.person_id,
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
        )
    )
    person = person_result.scalar_one_or_none()
    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kayıt edilecek kişi bu kulüpte bulunamadı.",
        )

    # Kapasite kontrolü
    if course.capacity > 0:
        cnt = await _active_enrollment_count(course_id, club_id, db)
        if cnt >= course.capacity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Kurs kapasitesi dolu ({course.capacity} kişi).",
            )

    # Aktif duplicate kontrolü
    dup = await db.execute(
        select(TrainingEnrollment).where(
            TrainingEnrollment.course_id == course_id,
            TrainingEnrollment.club_id == club_id,
            TrainingEnrollment.person_id == body.person_id,
            TrainingEnrollment.status == "active",
            TrainingEnrollment.is_deleted.is_(False),
        )
    )
    if dup.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu kişi bu kursa zaten aktif olarak kayıtlı.",
        )

    enrollment = TrainingEnrollment(
        club_id=club_id,
        course_id=course_id,
        person_id=body.person_id,
        notes=body.notes,
    )
    db.add(enrollment)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu kişi bu kursa zaten kayıtlı.",
        )

    await log_action(
        db,
        action="training_enrollment_created",
        resource_type="training_enrollment",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(enrollment.id),
        after={"course_id": str(course_id), "person_id": str(body.person_id)},
        request=request,
    )

    out = TrainingEnrollmentOut.model_validate(enrollment)
    out.person_name = _person_name(person)
    return out


@router.delete(
    "/{course_id}/participants/{person_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_participant(
    course_id: uuid.UUID,
    person_id: uuid.UUID,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("egitim:write")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _get_course(course_id, club_id, db)

    result = await db.execute(
        select(TrainingEnrollment).where(
            TrainingEnrollment.course_id == course_id,
            TrainingEnrollment.club_id == club_id,
            TrainingEnrollment.person_id == person_id,
            TrainingEnrollment.status == "active",
            TrainingEnrollment.is_deleted.is_(False),
        )
    )
    enrollment = result.scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aktif kayıt bulunamadı.",
        )

    enrollment.status = "cancelled"
    enrollment.cancelled_at = datetime.now(tz=timezone.utc)
    await db.flush()

    await log_action(
        db,
        action="training_enrollment_cancelled",
        resource_type="training_enrollment",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(enrollment.id),
        after={"course_id": str(course_id), "person_id": str(person_id), "status": "cancelled"},
        request=request,
    )


# ─── Oturumlar (Sessions) ─────────────────────────────────────────────────────

@router.get("/{course_id}/sessions", response_model=List[TrainingSessionOut])
async def list_sessions(
    course_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    _: None = Depends(require_permission("egitim:read")),
    db: AsyncSession = Depends(get_db),
) -> List[TrainingSessionOut]:
    await _get_course(course_id, club_id, db)

    result = await db.execute(
        select(TrainingSession)
        .where(
            TrainingSession.course_id == course_id,
            TrainingSession.club_id == club_id,
        )
        .order_by(TrainingSession.session_date, TrainingSession.start_time)
    )
    sessions = result.scalars().all()

    items = []
    for s in sessions:
        # Yoklama sayısı
        att_count_result = await db.execute(
            select(func.count()).where(TrainingAttendance.session_id == s.id)
        )
        att_count = att_count_result.scalar_one()
        out = TrainingSessionOut.model_validate(s)
        out.attendance_count = att_count
        items.append(out)
    return items


@router.post(
    "/{course_id}/sessions",
    response_model=TrainingSessionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    course_id: uuid.UUID,
    body: TrainingSessionCreate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("egitim:write")),
    db: AsyncSession = Depends(get_db),
) -> TrainingSessionOut:
    await _get_course(course_id, club_id, db)

    # Oturuma özel eğitmen bu kulüpte var mı?
    if body.instructor_person_id is not None:
        p = await db.execute(
            select(Person).where(
                Person.id == body.instructor_person_id,
                Person.club_id == club_id,
                Person.is_deleted.is_(False),
            )
        )
        if p.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Eğitmen olarak atanacak kişi bu kulüpte bulunamadı.",
            )

    session = TrainingSession(
        club_id=club_id,
        course_id=course_id,
        session_date=body.session_date,
        start_time=body.start_time,
        end_time=body.end_time,
        instructor_person_id=body.instructor_person_id,
        notes=body.notes,
        status=body.status,
    )
    db.add(session)
    await db.flush()

    await log_action(
        db,
        action="training_session_created",
        resource_type="training_session",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(session.id),
        after={"course_id": str(course_id), "session_date": str(body.session_date)},
        request=request,
    )

    await emit_event(
        db,
        club_id=club_id,
        event_type="training.session.created",
        aggregate_type="training_session",
        aggregate_id=session.id,
        payload={
            "course_id": str(course_id),
            "session_date": str(body.session_date),
            "start_time": str(body.start_time) if body.start_time else None,
        },
    )

    out = TrainingSessionOut.model_validate(session)
    out.attendance_count = 0
    return out


@router.patch("/{course_id}/sessions/{session_id}", response_model=TrainingSessionOut)
async def update_session(
    course_id: uuid.UUID,
    session_id: uuid.UUID,
    body: TrainingSessionUpdate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("egitim:write")),
    db: AsyncSession = Depends(get_db),
) -> TrainingSessionOut:
    session = await _get_session(session_id, course_id, club_id, db)
    update_data = body.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(session, field, value)
    await db.flush()
    # Server-side updated_at değerini response serialization öncesi yükle.
    await db.refresh(session)

    await log_action(
        db,
        action="training_session_updated",
        resource_type="training_session",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(session.id),
        after={k: str(v) for k, v in update_data.items()},
        request=request,
    )

    att_count_result = await db.execute(
        select(func.count()).where(TrainingAttendance.session_id == session.id)
    )
    att_count = att_count_result.scalar_one()
    out = TrainingSessionOut.model_validate(session)
    out.attendance_count = att_count
    return out


# ─── Yoklama ──────────────────────────────────────────────────────────────────

@router.get(
    "/{course_id}/sessions/{session_id}/attendance",
    response_model=List[TrainingAttendanceOut],
)
async def get_attendance(
    course_id: uuid.UUID,
    session_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    _: None = Depends(require_permission("yoklama:read")),
    db: AsyncSession = Depends(get_db),
) -> List[TrainingAttendanceOut]:
    await _get_session(session_id, course_id, club_id, db)

    result = await db.execute(
        select(TrainingAttendance)
        .options(selectinload(TrainingAttendance.person))
        .where(
            TrainingAttendance.session_id == session_id,
            TrainingAttendance.club_id == club_id,
        )
        .order_by(TrainingAttendance.created_at)
    )
    records = result.scalars().all()

    items = []
    for r in records:
        out = TrainingAttendanceOut.model_validate(r)
        out.person_name = _person_name(r.person)
        items.append(out)
    return items


@router.put(
    "/{course_id}/sessions/{session_id}/attendance",
    response_model=AttendanceBulkResult,
)
async def bulk_update_attendance(
    course_id: uuid.UUID,
    session_id: uuid.UUID,
    body: AttendanceBulkUpdate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("yoklama:write")),
    db: AsyncSession = Depends(get_db),
) -> AttendanceBulkResult:
    """Toplu yoklama UPSERT — varsa güncelle, yoksa oluştur.

    Eski Flask davranışı:
      for k in d.get('kayitlar', []):
          m = qone(... WHERE kurs_id AND sporcu_id AND tarih AND kulup_id)
          if m: UPDATE ... else: INSERT ...
    """
    session = await _get_session(session_id, course_id, club_id, db)
    user_id = uuid.UUID(current_user.sub)

    created = 0
    updated = 0

    for rec in body.records:
        existing = await db.execute(
            select(TrainingAttendance).where(
                TrainingAttendance.session_id == session_id,
                TrainingAttendance.person_id == rec.person_id,
                TrainingAttendance.club_id == club_id,
            )
        )
        att = existing.scalar_one_or_none()

        if att is not None:
            att.status = rec.status.value
            att.check_in_time = rec.check_in_time
            att.check_out_time = rec.check_out_time
            att.notes = rec.notes
            att.recorded_by_user_id = user_id
            updated += 1
        else:
            att = TrainingAttendance(
                club_id=club_id,
                session_id=session_id,
                person_id=rec.person_id,
                status=rec.status.value,
                check_in_time=rec.check_in_time,
                check_out_time=rec.check_out_time,
                notes=rec.notes,
                recorded_by_user_id=user_id,
            )
            db.add(att)
            created += 1

    await db.flush()

    await log_action(
        db,
        action="training_attendance_bulk_update",
        resource_type="training_attendance",
        club_id=club_id,
        user_id=user_id,
        resource_id=str(session_id),
        after={
            "session_id": str(session_id),
            "created": created,
            "updated": updated,
            "session_date": str(session.session_date),
        },
        request=request,
    )

    return AttendanceBulkResult(created=created, updated=updated)


# ─── Devam Raporu ─────────────────────────────────────────────────────────────

@router.get("/{course_id}/attendance/report", response_model=AttendanceReport)
async def attendance_report(
    course_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    _: None = Depends(require_permission("yoklama:read")),
    db: AsyncSession = Depends(get_db),
) -> AttendanceReport:
    """Kurs bazlı devam raporu — kişi başına var/yok/izinli/gecikti sayıları."""
    course = await _get_course(course_id, club_id, db)

    # Tüm oturumlar
    sessions_result = await db.execute(
        select(TrainingSession).where(
            TrainingSession.course_id == course_id,
            TrainingSession.club_id == club_id,
        )
    )
    sessions = sessions_result.scalars().all()
    session_ids = [s.id for s in sessions]

    if not session_ids:
        return AttendanceReport(
            course_id=course_id,
            course_name=course.name,
            toplam_oturum=0,
            katilimcilar=[],
        )

    # Tüm yoklama kayıtları
    att_result = await db.execute(
        select(TrainingAttendance)
        .options(selectinload(TrainingAttendance.person))
        .where(
            TrainingAttendance.session_id.in_(session_ids),
            TrainingAttendance.club_id == club_id,
        )
    )
    records = att_result.scalars().all()

    # Kişi bazlı topla
    summary: dict[uuid.UUID, AttendancePersonSummary] = {}
    for r in records:
        if r.person_id not in summary:
            summary[r.person_id] = AttendancePersonSummary(
                person_id=r.person_id,
                person_name=_person_name(r.person) or str(r.person_id),
            )
        s = summary[r.person_id]
        s.toplam_oturum += 1
        if r.status == "var":
            s.var += 1
        elif r.status == "yok":
            s.yok += 1
        elif r.status == "izinli":
            s.izinli += 1
        elif r.status == "gecikti":
            s.gecikti += 1

    # Devam yüzdesi = (var + gecikti) / toplam
    toplam_oturum = len(sessions)
    for s in summary.values():
        if s.toplam_oturum > 0:
            s.devam_yuzdesi = round(
                (s.var + s.gecikti) / toplam_oturum * 100, 1
            )

    return AttendanceReport(
        course_id=course_id,
        course_name=course.name,
        toplam_oturum=toplam_oturum,
        katilimcilar=sorted(summary.values(), key=lambda x: x.person_name),
    )
