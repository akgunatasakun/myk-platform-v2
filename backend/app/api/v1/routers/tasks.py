"""Görev CRUD: yönetim tüm görevleri, çalışan yalnız kendi görevlerini görür."""

import uuid
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import case, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.person import Person
from app.models.task import Task
from app.models.user import User
from app.schemas.auth import TokenPayload
from app.schemas.task import (
    TaskAssignee,
    TaskCreate,
    TaskListOut,
    TaskOut,
    TaskPriority,
    TaskStatus,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])
MANAGERS = {
    "super_admin",
    "kulup_yonetici",
    "genel_sekreter",
    "sportif_direktor",
    "basantrenor",
}
READ_ALL = MANAGERS | {"baskan", "yk_uyesi"}
WORKERS = {"antrenor", "personel", "muhasebe", "saglik_sorumlusu", "guvenlik_operasyon"}


async def scope(
    user: Annotated[TokenPayload, Depends(get_current_user)],
    club_id: Annotated[uuid.UUID, Depends(get_club_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if user.role not in READ_ALL | WORKERS:
        raise HTTPException(403, "Görev yönetimine erişim yetkiniz yok.")
    account = (
        await db.execute(
            select(User).where(
                User.id == uuid.UUID(user.sub),
                User.club_id == club_id,
                User.is_active.is_(True),
                User.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(403, "Aktif kullanıcı bulunamadı.")
    return user, club_id, account.person_id


def manager(ctx):
    if ctx[0].role not in MANAGERS:
        raise HTTPException(403, "Bu işlem için görev yönetimi yetkisi gerekir.")


def conditions(ctx):
    user, club_id, person_id = ctx
    result = [Task.club_id == club_id, Task.is_deleted.is_(False)]
    if user.role not in READ_ALL:
        result.append(Task.assigned_person_id == person_id if person_id else false())
    return result


def assignee_query(club_id):
    return select(Person).where(
        Person.club_id == club_id,
        Person.is_active.is_(True),
        Person.is_deleted.is_(False),
        Person.roles.any(role_code="antrenor") | Person.roles.any(role_code="personel"),
    )


async def validate_assignee(db, club_id, person_id):
    if (
        person_id
        and (
            await db.execute(assignee_query(club_id).where(Person.id == person_id))
        ).scalar_one_or_none()
        is None
    ):
        raise HTTPException(
            422,
            "Sorumlu, kulübün aktif antrenör veya personel kayıtlarından seçilmelidir.",
        )


def out(task, first=None, last=None):
    data = {
        key: getattr(task, key) for key in TaskOut.model_fields if hasattr(task, key)
    }
    data["assigned_person_name"] = f"{first} {last}".strip() if first else None
    return TaskOut(**data)


async def get_task(db, ctx, task_id):
    row = (
        await db.execute(
            select(Task, Person.first_name, Person.last_name)
            .outerjoin(
                Person,
                (Person.id == Task.assigned_person_id)
                & (Person.club_id == Task.club_id)
                & Person.is_deleted.is_(False),
            )
            .where(*conditions(ctx), Task.id == task_id)
        )
    ).first()
    if row is None:
        raise HTTPException(404, "Görev bulunamadı.")
    return row


@router.get("/assignees", response_model=list[TaskAssignee])
async def assignees(
    ctx: Annotated[tuple, Depends(scope)], db: Annotated[AsyncSession, Depends(get_db)]
):
    manager(ctx)
    people = (
        (
            await db.execute(
                assignee_query(ctx[1]).order_by(
                    Person.first_name, Person.last_name, Person.id
                )
            )
        )
        .scalars()
        .all()
    )
    return [TaskAssignee(id=p.id, name=f"{p.first_name} {p.last_name}") for p in people]


@router.get("", response_model=TaskListOut)
async def list_tasks(
    ctx: Annotated[tuple, Depends(scope)],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = Query(None, max_length=200),
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    assigned_person_id: uuid.UUID | None = None,
    open_only: bool = False,
    overdue_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
):
    filters = conditions(ctx)
    if search and search.strip():
        value = (
            search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        filters.append(
            or_(
                Task.title.ilike(f"%{value}%", escape="\\"),
                Task.description.ilike(f"%{value}%", escape="\\"),
            )
        )
    if status:
        filters.append(Task.status == status)
    if priority:
        filters.append(Task.priority == priority)
    if assigned_person_id:
        filters.append(Task.assigned_person_id == assigned_person_id)
    if open_only or overdue_only:
        filters.append(Task.status.in_(["acik", "devam_ediyor"]))
    if overdue_only:
        filters.append(Task.due_date < datetime.now(ZoneInfo("Europe/Istanbul")).date())
    total = (
        await db.execute(select(func.count()).select_from(Task).where(*filters))
    ).scalar_one()
    rows = (
        await db.execute(
            select(Task, Person.first_name, Person.last_name)
            .outerjoin(
                Person,
                (Person.id == Task.assigned_person_id)
                & (Person.club_id == Task.club_id)
                & Person.is_deleted.is_(False),
            )
            .where(*filters)
            .order_by(
                Task.due_date.asc().nullslast(),
                case(
                    (Task.priority == "acil", 0),
                    (Task.priority == "yuksek", 1),
                    (Task.priority == "normal", 2),
                    else_=3,
                ),
                Task.created_at.desc(),
                Task.id,
            )
            .offset(skip)
            .limit(limit)
        )
    ).all()
    return TaskListOut(
        items=[out(*row) for row in rows], total=total, skip=skip, limit=limit
    )


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    data: TaskCreate,
    request: Request,
    ctx: Annotated[tuple, Depends(scope)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    manager(ctx)
    await validate_assignee(db, ctx[1], data.assigned_person_id)
    task = Task(club_id=ctx[1], **data.model_dump())
    db.add(task)
    await db.flush()
    await log_action(
        db,
        action="task_created",
        resource_type="task",
        resource_id=str(task.id),
        club_id=ctx[1],
        user_id=uuid.UUID(ctx[0].sub),
        after=data.model_dump(mode="json"),
        request=request,
    )
    return out(*(await get_task(db, ctx, task.id)))


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    request: Request,
    ctx: Annotated[tuple, Depends(scope)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    task, _, _ = await get_task(db, ctx, task_id)
    changes = data.model_dump(exclude_unset=True)
    if ctx[0].role not in MANAGERS and (
        ctx[0].role not in WORKERS or set(changes) - {"status"}
    ):
        raise HTTPException(
            403, "Yalnız size atanan görevin durumunu değiştirebilirsiniz."
        )
    if (
        "assigned_person_id" in changes
        and changes["assigned_person_id"] != task.assigned_person_id
    ):
        await validate_assignee(db, ctx[1], changes["assigned_person_id"])
    before = {
        key: str(getattr(task, key)) if getattr(task, key) is not None else None
        for key in changes
    }
    for key, value in changes.items():
        setattr(task, key, value)
    await db.flush()
    await log_action(
        db,
        action="task_updated",
        resource_type="task",
        resource_id=str(task.id),
        club_id=ctx[1],
        user_id=uuid.UUID(ctx[0].sub),
        before=before,
        after=data.model_dump(mode="json", exclude_unset=True),
        request=request,
    )
    return out(*(await get_task(db, ctx, task.id)))


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: uuid.UUID,
    request: Request,
    ctx: Annotated[tuple, Depends(scope)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    manager(ctx)
    task, _, _ = await get_task(db, ctx, task_id)
    task.is_deleted = True
    await log_action(
        db,
        action="task_deleted",
        resource_type="task",
        resource_id=str(task.id),
        club_id=ctx[1],
        user_id=uuid.UUID(ctx[0].sub),
        request=request,
    )
    await db.flush()
    return Response(status_code=204)
