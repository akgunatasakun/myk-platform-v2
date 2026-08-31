"""Training (Fiziksel Eğitim) API router — kurs, oturum, kayıt, yoklama.

Endpoint listesi:
  GET    /trainings                                         → kurs listesi
  POST   /trainings                                         → kurs oluştur
  GET    /trainings/{course_id}                             → kurs detay
  PATCH  /trainings/{course_id}                             → kurs güncelle
  DELETE /trainings/{course_id}                             → kurs soft-delete

  GET    /trainings/{course_id}/participants                → kayıt listesi (sadece aktif)
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
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import log_action
from app.core.rbac import require_permission, is_own_scope_only
from app.services.event_service import emit_event
from app.services.training_scope_service import get_antrenor_course_ids
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.person import Person, PersonRole
from app.models.person_guardian import PersonGuardian
from app.models.user import User
from app.models.training import (
    TrainingAttendance,
    TrainingCourse,
    TrainingCourseInstructor,
    TrainingEnrollment,
    TrainingSession,
    TrainingSessionInstructor,
)
from app.schemas.auth import TokenPayload
from app.schemas.training import (
    AttendanceBulkResult,
    AttendanceBulkUpdate,
    AttendanceMode,
    AttendancePersonSummary,
    AttendanceReport,
    AttendanceStatus,
    InstructorRef,
    SelfCheckinSessionOut,
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
_ISTANBUL = ZoneInfo("Europe/Istanbul")


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


async def _get_own_person_ids(
    user_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
    role: str,
) -> list[uuid.UUID]:
    """Own-scope için erişilebilir person_id listesi döndür.

    - sporcu: [kendi person_id]
    - veli: [ward'larının person_id listesi]
    - diğer: [] (own-scope beklenmiyor)
    """
    result = await db.execute(select(User.person_id).where(User.id == user_id))
    person_id: uuid.UUID | None = result.scalar_one_or_none()
    if not person_id:
        return []

    if role == "sporcu":
        return [person_id]

    if role == "veli":
        result = await db.execute(
            select(PersonGuardian.athlete_person_id).where(
                PersonGuardian.guardian_person_id == person_id,
                PersonGuardian.club_id == club_id,
            )
        )
        return list(result.scalars().all())

    return []


async def _assert_own_scope_course_access(
    course_id: uuid.UUID,
    person_ids: list[uuid.UUID],
    club_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Sporcu/veli için kurs erişim kontrolü: kayıtlı değilse 403."""
    if not person_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu kursa erişim yetkiniz yok.",
        )
    result = await db.execute(
        select(TrainingEnrollment.id).where(
            TrainingEnrollment.course_id == course_id,
            TrainingEnrollment.person_id.in_(person_ids),
            TrainingEnrollment.club_id == club_id,
            TrainingEnrollment.status == "active",
            TrainingEnrollment.is_deleted.is_(False),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu kursa erişim yetkiniz yok.",
        )


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


async def _load_course_instructors(
    course_id: uuid.UUID, club_id: uuid.UUID, db: AsyncSession
) -> List[InstructorRef]:
    """Kurs antrenörlerini junction tablosundan yükle."""
    result = await db.execute(
        select(TrainingCourseInstructor)
        .options(selectinload(TrainingCourseInstructor.person))
        .where(
            TrainingCourseInstructor.course_id == course_id,
            TrainingCourseInstructor.club_id == club_id,
        )
        .order_by(TrainingCourseInstructor.created_at)
    )
    rows = result.scalars().all()
    return [
        InstructorRef(id=r.person_id, name=_person_name(r.person) or str(r.person_id))
        for r in rows
        if r.person is not None
    ]


async def _load_session_instructors(
    session_id: uuid.UUID, club_id: uuid.UUID, db: AsyncSession
) -> List[InstructorRef]:
    """Oturum antrenörlerini junction tablosundan yükle."""
    result = await db.execute(
        select(TrainingSessionInstructor)
        .options(selectinload(TrainingSessionInstructor.person))
        .where(
            TrainingSessionInstructor.session_id == session_id,
            TrainingSessionInstructor.club_id == club_id,
        )
        .order_by(TrainingSessionInstructor.created_at)
    )
    rows = result.scalars().all()
    return [
        InstructorRef(id=r.person_id, name=_person_name(r.person) or str(r.person_id))
        for r in rows
        if r.person is not None
    ]


async def _validate_instructors(
    instructor_ids: List[uuid.UUID],
    club_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Her person_id: aynı kulüpte aktif + antrenor rolü var mı?

    Raises HTTPException 422 on first violation.
    """
    for pid in instructor_ids:
        person_result = await db.execute(
            select(Person).where(
                Person.id == pid,
                Person.club_id == club_id,
                Person.is_active.is_(True),
                Person.is_deleted.is_(False),
            )
        )
        person = person_result.scalar_one_or_none()
        if person is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Antrenör olarak atanacak kişi bu kulüpte bulunamadı: {pid}",
            )
        role_result = await db.execute(
            select(PersonRole).where(
                PersonRole.person_id == pid,
                PersonRole.role_code == "antrenor",
            )
        )
        if role_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Kişinin 'antrenor' rolü yok: {pid}",
            )


async def _set_course_instructors(
    course_id: uuid.UUID,
    club_id: uuid.UUID,
    instructor_ids: List[uuid.UUID],
    db: AsyncSession,
    *,
    replace: bool = True,
) -> None:
    """Junction tablosunu güncelle.

    replace=True: mevcut kayıtları sil, yeniden ekle.
    replace=False: sadece ekle (duplicate'i yoksay).
    """
    if replace:
        existing = await db.execute(
            select(TrainingCourseInstructor).where(
                TrainingCourseInstructor.course_id == course_id,
                TrainingCourseInstructor.club_id == club_id,
            )
        )
        for row in existing.scalars().all():
            await db.delete(row)
        await db.flush()

    for pid in instructor_ids:
        if not replace:
            dup = await db.execute(
                select(TrainingCourseInstructor).where(
                    TrainingCourseInstructor.course_id == course_id,
                    TrainingCourseInstructor.person_id == pid,
                )
            )
            if dup.scalar_one_or_none() is not None:
                continue
        db.add(TrainingCourseInstructor(
            club_id=club_id,
            course_id=course_id,
            person_id=pid,
        ))
    await db.flush()


async def _set_session_instructors(
    session_id: uuid.UUID,
    club_id: uuid.UUID,
    instructor_ids: List[uuid.UUID],
    db: AsyncSession,
    *,
    replace: bool = True,
) -> None:
    if replace:
        existing = await db.execute(
            select(TrainingSessionInstructor).where(
                TrainingSessionInstructor.session_id == session_id,
                TrainingSessionInstructor.club_id == club_id,
            )
        )
        for row in existing.scalars().all():
            await db.delete(row)
        await db.flush()

    for pid in instructor_ids:
        if not replace:
            dup = await db.execute(
                select(TrainingSessionInstructor).where(
                    TrainingSessionInstructor.session_id == session_id,
                    TrainingSessionInstructor.person_id == pid,
                )
            )
            if dup.scalar_one_or_none() is not None:
                continue
        db.add(TrainingSessionInstructor(
            club_id=club_id,
            session_id=session_id,
            person_id=pid,
        ))
    await db.flush()


def _apply_instructors_to_course_out(out: TrainingCourseOut, instructors: List[InstructorRef]) -> None:
    """Çıktı nesnesine antrenör verilerini yaz (eski + yeni alanlar)."""
    out.instructors = instructors
    if instructors:
        out.instructor_person_id = instructors[0].id
        out.instructor_name = instructors[0].name
    else:
        out.instructor_person_id = None
        out.instructor_name = None


def _apply_instructors_to_session_out(out: TrainingSessionOut, instructors: List[InstructorRef]) -> None:
    out.instructors = instructors
    if instructors:
        out.instructor_person_id = instructors[0].id
        out.instructor_name = instructors[0].name
    else:
        out.instructor_person_id = None
        out.instructor_name = None


# ─── Sporcu Self Check-in Oturumları ──────────────────────────────────────────
# NOT: Bu endpoint /me/... path'i kullanır ve /{course_id}/... önünde tanımlanmalı.

@router.get("/me/self-checkin-sessions", response_model=List[SelfCheckinSessionOut])
async def get_self_checkin_sessions(
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SelfCheckinSessionOut]:
    """Sporcunun adult_self_checkin modlu kurslarındaki oturumları döndürür.

    Sadece bugün ve sonraki 14 günü kapsar (geçmiş oturumlar gösterilmez).
    Her oturum için pencere durumu ve kişinin mevcut attendance kaydı da döner.
    Sporcu rolü gerektirir (egitim:read:own).
    """
    user_id = uuid.UUID(current_user.sub)

    # Kullanıcı → person
    user_q = await db.execute(
        select(User).where(
            User.id == user_id,
            User.club_id == club_id,
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        )
    )
    user_obj = user_q.scalar_one_or_none()
    if user_obj is None or user_obj.person_id is None or user_obj.role != "sporcu":
        return []
    person_id = user_obj.person_id

    person_q = await db.execute(
        select(Person).where(
            Person.id == person_id,
            Person.club_id == club_id,
            Person.is_active.is_(True),
            Person.is_deleted.is_(False),
        )
    )
    if person_q.scalar_one_or_none() is None:
        return []

    today = datetime.now(_ISTANBUL).date()
    horizon = today + timedelta(days=14)

    # Aktif enrollments → adult_self_checkin kursları
    enr_q = await db.execute(
        select(TrainingEnrollment, TrainingCourse)
        .join(TrainingCourse, TrainingEnrollment.course_id == TrainingCourse.id)
        .where(
            TrainingEnrollment.person_id == person_id,
            TrainingEnrollment.club_id == club_id,
            TrainingEnrollment.status == "active",
            TrainingEnrollment.is_deleted.is_(False),
            TrainingCourse.attendance_mode == AttendanceMode.adult_self_checkin.value,
            TrainingCourse.status == "aktif",
            TrainingCourse.is_active.is_(True),
            TrainingCourse.is_deleted.is_(False),
        )
    )
    enrollments = enr_q.all()

    if not enrollments:
        return []

    course_ids = [row.TrainingCourse.id for row in enrollments]
    course_map = {row.TrainingCourse.id: row.TrainingCourse for row in enrollments}

    # Oturumlar — bugün + 14 gün
    sessions_q = await db.execute(
        select(TrainingSession).where(
            TrainingSession.course_id.in_(course_ids),
            TrainingSession.club_id == club_id,
            TrainingSession.session_date >= today,
            TrainingSession.session_date <= horizon,
            TrainingSession.status != "iptal",
        ).order_by(TrainingSession.session_date, TrainingSession.start_time)
    )
    sessions = sessions_q.scalars().all()

    if not sessions:
        return []

    session_ids = [s.id for s in sessions]

    # Mevcut attendance kayıtları
    att_q = await db.execute(
        select(TrainingAttendance).where(
            TrainingAttendance.session_id.in_(session_ids),
            TrainingAttendance.person_id == person_id,
            TrainingAttendance.club_id == club_id,
        )
    )
    att_map: dict[uuid.UUID, TrainingAttendance] = {
        a.session_id: a for a in att_q.scalars()
    }

    result: List[SelfCheckinSessionOut] = []
    for s in sessions:
        course = course_map.get(s.course_id)
        if course is None:
            continue

        open_flag = _check_in_window_open(s)

        if s.start_time and s.end_time:
            window_note = (
                f"{s.start_time.strftime('%H:%M')} – {s.end_time.strftime('%H:%M')} "
                "arasında açık (±30/60 dk)"
            )
        else:
            window_note = "Tüm gün açık (yalnızca oturum günü)"

        existing_att = att_map.get(s.id)

        result.append(SelfCheckinSessionOut(
            session_id=s.id,
            course_id=course.id,
            course_name=course.name,
            session_date=s.session_date,
            start_time=s.start_time,
            end_time=s.end_time,
            window_open=open_flag,
            window_note=window_note,
            my_status=existing_att.status if existing_att else None,
        ))

    return result


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

    # Scope filtresi: sporcu/veli → kayıtlı kurslar; antrenör → atandığı kurslar
    if is_own_scope_only(current_user.role, "egitim:read"):
        person_ids = await _get_own_person_ids(
            uuid.UUID(current_user.sub), club_id, db, current_user.role
        )
        if not person_ids:
            return TrainingCourseListOut(items=[], total=0, skip=skip, limit=limit)
        enrolled_course_ids = select(TrainingEnrollment.course_id).where(
            TrainingEnrollment.person_id.in_(person_ids),
            TrainingEnrollment.club_id == club_id,
            TrainingEnrollment.status == "active",
            TrainingEnrollment.is_deleted.is_(False),
        )
        q = q.where(TrainingCourse.id.in_(enrolled_course_ids))
    elif current_user.role == "antrenor":
        allowed = await get_antrenor_course_ids(uuid.UUID(current_user.sub), club_id, db)
        if not allowed:
            return TrainingCourseListOut(items=[], total=0, skip=skip, limit=limit)
        q = q.where(TrainingCourse.id.in_(allowed))

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
        instructors = await _load_course_instructors(c.id, club_id, db)
        out = TrainingCourseOut.model_validate(c)
        out.enrollment_count = cnt
        _apply_instructors_to_course_out(out, instructors)
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
    instructor_ids = body.effective_instructor_ids()

    if instructor_ids:
        await _validate_instructors(instructor_ids, club_id, db)

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
        # instructor_person_id legacy sütunu: ilk antrenörden doldur
        instructor_person_id=instructor_ids[0] if instructor_ids else None,
        status=body.status,
        attendance_mode=body.attendance_mode.value,
        is_registration_open=body.is_registration_open,
    )
    db.add(course)
    await db.flush()

    # Junction tabloya yaz
    if instructor_ids:
        await _set_course_instructors(course.id, club_id, instructor_ids, db, replace=False)

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

    instructors = await _load_course_instructors(course.id, club_id, db)
    out = TrainingCourseOut.model_validate(course)
    out.enrollment_count = 0
    _apply_instructors_to_course_out(out, instructors)
    return out


@router.get("/{course_id}", response_model=TrainingCourseOut)
async def get_course(
    course_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("egitim:read")),
    db: AsyncSession = Depends(get_db),
) -> TrainingCourseOut:
    course = await _get_course(course_id, club_id, db)
    if is_own_scope_only(current_user.role, "egitim:read"):
        person_ids = await _get_own_person_ids(uuid.UUID(current_user.sub), club_id, db, current_user.role)
        await _assert_own_scope_course_access(course_id, person_ids, club_id, db)
    elif current_user.role == "antrenor":
        allowed = await get_antrenor_course_ids(uuid.UUID(current_user.sub), club_id, db)
        if course_id not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu kursa erişim yetkiniz yok.")
    cnt = await _active_enrollment_count(course_id, club_id, db)
    instructors = await _load_course_instructors(course_id, club_id, db)
    out = TrainingCourseOut.model_validate(course)
    out.enrollment_count = cnt
    _apply_instructors_to_course_out(out, instructors)
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

    # Antrenör güncellemesi var mı?
    if body.has_instructor_update():
        new_instructor_ids = body.effective_instructor_ids()
        if new_instructor_ids:
            await _validate_instructors(new_instructor_ids, club_id, db)
        await _set_course_instructors(course_id, club_id, new_instructor_ids, db, replace=True)
        # Legacy sütunu da güncelle
        course.instructor_person_id = new_instructor_ids[0] if new_instructor_ids else None

    # Diğer alanları güncelle (antrenör alanları hariç)
    update_data = body.model_dump(
        exclude_unset=True,
        exclude={"instructor_person_id", "instructor_person_ids"},
    )

    if update_data:
        before = {k: str(getattr(course, k)) for k in update_data if hasattr(course, k)}
        for field, value in update_data.items():
            # Enum değerlerini str'e çevir (ORM Text sütunları için)
            if hasattr(value, "value"):
                value = value.value
            setattr(course, field, value)
        await db.flush()
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
    elif body.has_instructor_update():
        await db.flush()
        await db.refresh(course)

    cnt = await _active_enrollment_count(course_id, club_id, db)
    instructors = await _load_course_instructors(course_id, club_id, db)
    out = TrainingCourseOut.model_validate(course)
    out.enrollment_count = cnt
    _apply_instructors_to_course_out(out, instructors)
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
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("egitim:read")),
    db: AsyncSession = Depends(get_db),
) -> List[TrainingEnrollmentOut]:
    """Aktif kayıtlı katılımcıları döndür.

    P0-1 fix: status='active' filtresi eklendi — iptal kayıtlar hariç tutulur.
    RBAC Phase 3: sporcu/veli yalnızca kendi kaydını görür.
    """
    await _get_course(course_id, club_id, db)

    enrollment_q = (
        select(TrainingEnrollment)
        .options(selectinload(TrainingEnrollment.person))
        .where(
            TrainingEnrollment.course_id == course_id,
            TrainingEnrollment.club_id == club_id,
            TrainingEnrollment.status == "active",        # P0-1 fix
            TrainingEnrollment.is_deleted.is_(False),
        )
        .order_by(TrainingEnrollment.enrolled_at)
    )
    # Scope: sporcu/veli → kendi kaydı + kurs erişim kontrolü; antrenör → kurs erişim kontrolü
    if is_own_scope_only(current_user.role, "egitim:read"):
        person_ids = await _get_own_person_ids(
            uuid.UUID(current_user.sub), club_id, db, current_user.role
        )
        await _assert_own_scope_course_access(course_id, person_ids, club_id, db)
        enrollment_q = enrollment_q.where(TrainingEnrollment.person_id.in_(person_ids))
    elif current_user.role == "antrenor":
        allowed = await get_antrenor_course_ids(uuid.UUID(current_user.sub), club_id, db)
        if course_id not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu kursa erişim yetkiniz yok.")

    result = await db.execute(enrollment_q)
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
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("egitim:read")),
    db: AsyncSession = Depends(get_db),
) -> List[TrainingSessionOut]:
    await _get_course(course_id, club_id, db)
    if is_own_scope_only(current_user.role, "egitim:read"):
        person_ids = await _get_own_person_ids(uuid.UUID(current_user.sub), club_id, db, current_user.role)
        await _assert_own_scope_course_access(course_id, person_ids, club_id, db)
    elif current_user.role == "antrenor":
        allowed = await get_antrenor_course_ids(uuid.UUID(current_user.sub), club_id, db)
        if course_id not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu kursa erişim yetkiniz yok.")

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
        att_count_result = await db.execute(
            select(func.count()).where(TrainingAttendance.session_id == s.id)
        )
        att_count = att_count_result.scalar_one()
        instructors = await _load_session_instructors(s.id, club_id, db)
        out = TrainingSessionOut.model_validate(s)
        out.attendance_count = att_count
        _apply_instructors_to_session_out(out, instructors)
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

    instructor_ids = body.effective_instructor_ids()
    if instructor_ids:
        await _validate_instructors(instructor_ids, club_id, db)

    session = TrainingSession(
        club_id=club_id,
        course_id=course_id,
        session_date=body.session_date,
        start_time=body.start_time,
        end_time=body.end_time,
        # Legacy sütun: ilk antrenörden
        instructor_person_id=instructor_ids[0] if instructor_ids else None,
        notes=body.notes,
        status=body.status,
    )
    db.add(session)
    await db.flush()

    if instructor_ids:
        await _set_session_instructors(session.id, club_id, instructor_ids, db, replace=False)

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

    instructors = await _load_session_instructors(session.id, club_id, db)
    out = TrainingSessionOut.model_validate(session)
    out.attendance_count = 0
    _apply_instructors_to_session_out(out, instructors)
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

    if body.has_instructor_update():
        new_instructor_ids = body.effective_instructor_ids()
        if new_instructor_ids:
            await _validate_instructors(new_instructor_ids, club_id, db)
        await _set_session_instructors(session_id, club_id, new_instructor_ids, db, replace=True)
        session.instructor_person_id = new_instructor_ids[0] if new_instructor_ids else None

    update_data = body.model_dump(
        exclude_unset=True,
        exclude={"instructor_person_id", "instructor_person_ids"},
    )

    if update_data:
        for field, value in update_data.items():
            setattr(session, field, value)
        await db.flush()
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
    elif body.has_instructor_update():
        await db.flush()
        await db.refresh(session)

    att_count_result = await db.execute(
        select(func.count()).where(TrainingAttendance.session_id == session.id)
    )
    att_count = att_count_result.scalar_one()
    instructors = await _load_session_instructors(session.id, club_id, db)
    out = TrainingSessionOut.model_validate(session)
    out.attendance_count = att_count
    _apply_instructors_to_session_out(out, instructors)
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
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("yoklama:read")),
    db: AsyncSession = Depends(get_db),
) -> List[TrainingAttendanceOut]:
    await _get_session(session_id, course_id, club_id, db)

    att_q = (
        select(TrainingAttendance)
        .options(selectinload(TrainingAttendance.person))
        .where(
            TrainingAttendance.session_id == session_id,
            TrainingAttendance.club_id == club_id,
        )
        .order_by(TrainingAttendance.created_at)
    )
    # Scope: sporcu/veli → kendi kaydı + kurs erişim kontrolü; antrenör → atandığı kurs
    if is_own_scope_only(current_user.role, "yoklama:read"):
        person_ids = await _get_own_person_ids(
            uuid.UUID(current_user.sub), club_id, db, current_user.role
        )
        await _assert_own_scope_course_access(course_id, person_ids, club_id, db)
        att_q = att_q.where(TrainingAttendance.person_id.in_(person_ids))
    elif current_user.role == "antrenor":
        allowed = await get_antrenor_course_ids(uuid.UUID(current_user.sub), club_id, db)
        if course_id not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu kursa erişim yetkiniz yok.")

    result = await db.execute(att_q)
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

    P0-1 fix: Her person_id'nin bu kursa aktif kayıtlı olduğu doğrulanır.
    """
    session = await _get_session(session_id, course_id, club_id, db)
    user_id = uuid.UUID(current_user.sub)

    # Antrenör scope: yalnızca atandığı kursa yoklama yazabilir
    if current_user.role == "antrenor":
        allowed = await get_antrenor_course_ids(user_id, club_id, db)
        if course_id not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu kursa yoklama yazma yetkiniz yok.")

    created = 0
    updated = 0
    # Override kayıtları — önceki/yeni değer audit log için
    overrides: list[dict] = []

    for rec in body.records:
        # P0-1: Enrollment doğrulaması — person bu kursa aktif kayıtlı olmalı
        enrollment_check = await db.execute(
            select(TrainingEnrollment).where(
                TrainingEnrollment.course_id == course_id,
                TrainingEnrollment.club_id == club_id,
                TrainingEnrollment.person_id == rec.person_id,
                TrainingEnrollment.status == "active",
                TrainingEnrollment.is_deleted.is_(False),
            )
        )
        if enrollment_check.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Kişi bu kursa aktif kayıtlı değil: {rec.person_id}",
            )

        existing = await db.execute(
            select(TrainingAttendance).where(
                TrainingAttendance.session_id == session_id,
                TrainingAttendance.person_id == rec.person_id,
                TrainingAttendance.club_id == club_id,
            )
        )
        att = existing.scalar_one_or_none()

        if att is not None:
            prev_status = att.status
            att.status = rec.status.value
            att.check_in_time = rec.check_in_time
            att.check_out_time = rec.check_out_time
            att.notes = rec.notes
            att.recorded_by_user_id = user_id
            updated += 1
            # Override varsa kaydet (durum değiştiyse)
            if prev_status != rec.status.value:
                overrides.append({
                    "person_id": str(rec.person_id),
                    "before": prev_status,
                    "after": rec.status.value,
                })
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

    if overrides:
        action = "training_attendance_coach_overridden"
    elif updated > 0:
        action = "training_attendance_coach_updated"
    else:
        action = "training_attendance_coach_created"
    await log_action(
        db,
        action=action,
        resource_type="training_attendance",
        club_id=club_id,
        user_id=user_id,
        resource_id=str(session_id),
        after={
            "session_id": str(session_id),
            "created": created,
            "updated": updated,
            "session_date": str(session.session_date),
            **({"overrides": overrides} if overrides else {}),
        },
        request=request,
    )

    return AttendanceBulkResult(created=created, updated=updated)


# ─── Self Check-in (Yetişkin) ─────────────────────────────────────────────────

def _check_in_window_open(session: TrainingSession) -> bool:
    """Oturum self-check-in penceresi açık mı? (Europe/Istanbul saati kullanılır)

    Kural:
      - start_time ve end_time ikisi de varsa:
          start_time - 30dk ≤ now_istanbul ≤ end_time + 60dk
      - Herhangi biri yoksa:
          Yalnızca oturum tarihinde (İstanbul saatiyle aynı gün) açık — geçmiş/gelecek günler kapalı.
    """
    now_istanbul = datetime.now(_ISTANBUL)

    if session.start_time is None or session.end_time is None:
        # Saatsiz fallback: yalnızca oturum tarihinde açık
        return now_istanbul.date() == session.session_date

    # Oturum start/end'i İstanbul saat dilimiyle oluştur
    session_start = datetime(
        session.session_date.year,
        session.session_date.month,
        session.session_date.day,
        session.start_time.hour,
        session.start_time.minute,
        tzinfo=_ISTANBUL,
    )
    session_end = datetime(
        session.session_date.year,
        session.session_date.month,
        session.session_date.day,
        session.end_time.hour,
        session.end_time.minute,
        tzinfo=_ISTANBUL,
    )
    window_open = session_start - timedelta(minutes=30)
    window_close = session_end + timedelta(minutes=60)
    return window_open <= now_istanbul <= window_close


def _calculate_age_on_date(birth_date: date, on_date: date) -> int:
    """on_date tarihindeki yaşı hesaplar."""
    return on_date.year - birth_date.year - (
        (on_date.month, on_date.day) < (birth_date.month, birth_date.day)
    )


@router.post(
    "/{course_id}/sessions/{session_id}/self-checkin",
    response_model=TrainingAttendanceOut,
    status_code=status.HTTP_200_OK,
)
async def self_checkin(
    course_id: uuid.UUID,
    session_id: uuid.UUID,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrainingAttendanceOut:
    """Yetişkin sporcu kendi check-in kaydını oluşturur (idempotent).

    Doğrulamalar:
      1. JWT kullanıcısının user.person_id bağlantısı olmalı.
      2. Kişi aynı kulüpte olmalı.
      3. Eğitim modu adult_self_checkin olmalı.
      4. Oturum bu kursa ait olmalı.
      5. Kişi bu kursa aktif kayıtlı olmalı.
      6. Sporcu oturum tarihinde en az 18 yaşında olmalı.
      7. start_time/end_time varsa zaman penceresi: -30 / +60 dk.
      8. Aynı (session_id, person_id) için kayıt zaten varsa — mevcut kayıt döner (idempotent).
    """
    user_id = uuid.UUID(current_user.sub)

    # 1. Kullanıcı → person bağlantısı
    user_q = await db.execute(
        select(User).where(
            User.id == user_id,
            User.club_id == club_id,
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        )
    )
    user_obj = user_q.scalar_one_or_none()
    if user_obj is None or user_obj.person_id is None or user_obj.role != "sporcu":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesabınız bir sporcu kaydına bağlı değil. Yöneticinizle iletişime geçin.",
        )
    person_id = user_obj.person_id

    # 2. Person — kulüp doğrulaması
    person_q = await db.execute(
        select(Person).where(
            Person.id == person_id,
            Person.club_id == club_id,
            Person.is_active.is_(True),
            Person.is_deleted.is_(False),
        )
    )
    person = person_q.scalar_one_or_none()
    if person is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu kulübün üyesi değilsiniz.",
        )

    # 3. Kurs — attendance_mode doğrulaması
    course_q = await db.execute(
        select(TrainingCourse).where(
            TrainingCourse.id == course_id,
            TrainingCourse.club_id == club_id,
            TrainingCourse.status == "aktif",
            TrainingCourse.is_active.is_(True),
            TrainingCourse.is_deleted.is_(False),
        )
    )
    course = course_q.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eğitim bulunamadı.")
    if course.attendance_mode != AttendanceMode.adult_self_checkin.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu eğitim self check-in modunda değil.",
        )

    # 4. Oturum — kursa ait olduğunu doğrula
    session = await _get_session(session_id, course_id, club_id, db)

    # 5. Aktif enrollment
    enr_q = await db.execute(
        select(TrainingEnrollment).where(
            TrainingEnrollment.course_id == course_id,
            TrainingEnrollment.club_id == club_id,
            TrainingEnrollment.person_id == person_id,
            TrainingEnrollment.status == "active",
            TrainingEnrollment.is_deleted.is_(False),
        )
    )
    if enr_q.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu eğitime kayıtlı değilsiniz.",
        )

    # 6. +18 yaş kontrolü (oturum tarihinde)
    # Doğum tarihi zorunlu — kayıtsız kişi check-in yapamaz
    if person.birth_date is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doğum tarihi kayıtlı olmayan kişiler self check-in yapamaz. Yöneticinizle iletişime geçin.",
        )
    age = _calculate_age_on_date(person.birth_date, session.session_date)
    if age < 18:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu özellik yalnızca 18 yaş ve üzeri sporcular içindir.",
        )

    # 7. Zaman penceresi
    if not _check_in_window_open(session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Check-in penceresi henüz açılmadı veya kapandı. "
                "Oturum başlangıcından 30 dakika önce ile bitişinden 60 dakika sonrasına kadar giriş yapabilirsiniz."
            ),
        )

    # 8. Idempotency — aynı kayıt zaten varsa döndür
    existing_q = await db.execute(
        select(TrainingAttendance).where(
            TrainingAttendance.session_id == session_id,
            TrainingAttendance.person_id == person_id,
            TrainingAttendance.club_id == club_id,
        )
    )
    att = existing_q.scalar_one_or_none()

    if att is not None:
        # Mevcut kayıt — "var" değilse güncelle (antrenör başka bir şey girmişse dokunma)
        # Self-check-in idempotent: kayıt zaten varsa olduğu gibi döner
        out = TrainingAttendanceOut.model_validate(att)
        out.person_name = f"{person.first_name} {person.last_name}".strip()
        return out

    # Yeni kayıt oluştur — eşzamanlı insert yarışı IntegrityError üretebilir
    att = TrainingAttendance(
        club_id=club_id,
        session_id=session_id,
        person_id=person_id,
        status=AttendanceStatus.var.value,
        recorded_by_user_id=user_id,
    )
    try:
        async with db.begin_nested():
            db.add(att)
            await db.flush()
    except IntegrityError:
        # Eşzamanlı başka bir istek aynı kaydı oluşturdu — mevcut kaydı dön (idempotent)
        race_q = await db.execute(
            select(TrainingAttendance).where(
                TrainingAttendance.session_id == session_id,
                TrainingAttendance.person_id == person_id,
                TrainingAttendance.club_id == club_id,
            )
        )
        att = race_q.scalar_one()
        out = TrainingAttendanceOut.model_validate(att)
        out.person_name = f"{person.first_name} {person.last_name}".strip()
        return out

    await db.refresh(att)

    await log_action(
        db,
        action="training_attendance_self_checkin",
        resource_type="training_attendance",
        club_id=club_id,
        user_id=user_id,
        resource_id=str(att.id),
        after={
            "session_id": str(session_id),
            "course_id": str(course_id),
            "person_id": str(person_id),
            "status": att.status,
            "session_date": str(session.session_date),
        },
        request=request,
    )

    out = TrainingAttendanceOut.model_validate(att)
    out.person_name = f"{person.first_name} {person.last_name}".strip()
    return out


# ─── Devam Raporu ─────────────────────────────────────────────────────────────

@router.get("/{course_id}/attendance/report", response_model=AttendanceReport)
async def attendance_report(
    course_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("yoklama:read")),
    db: AsyncSession = Depends(get_db),
) -> AttendanceReport:
    """Kurs bazlı devam raporu — kişi başına var/yok/izinli/gecikti sayıları."""
    course = await _get_course(course_id, club_id, db)

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

    att_q = (
        select(TrainingAttendance)
        .options(selectinload(TrainingAttendance.person))
        .where(
            TrainingAttendance.session_id.in_(session_ids),
            TrainingAttendance.club_id == club_id,
        )
    )
    # Scope: sporcu/veli → kendi kayıtları + kurs erişim kontrolü; antrenör → atandığı kurs kontrolü
    if is_own_scope_only(current_user.role, "yoklama:read"):
        person_ids = await _get_own_person_ids(
            uuid.UUID(current_user.sub), club_id, db, current_user.role
        )
        await _assert_own_scope_course_access(course_id, person_ids, club_id, db)
        att_q = att_q.where(TrainingAttendance.person_id.in_(person_ids))
    elif current_user.role == "antrenor":
        allowed = await get_antrenor_course_ids(uuid.UUID(current_user.sub), club_id, db)
        if course_id not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu kursa erişim yetkiniz yok.")
    att_result = await db.execute(att_q)
    records = att_result.scalars().all()

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
