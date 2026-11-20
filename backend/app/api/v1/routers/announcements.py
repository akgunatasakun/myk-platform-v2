"""Duyurular yalnız kulüp, hedef rol ve yayın aralığı içinde gösterilir."""

import uuid
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.announcement import Announcement, AnnouncementAudience
from app.schemas.announcement import (
    AnnouncementInput,
    AnnouncementList,
    AnnouncementOut,
    AnnouncementStatus,
)
from app.schemas.auth import TokenPayload

router = APIRouter(prefix="/announcements", tags=["announcements"])
MANAGERS = {"super_admin", "kulup_yonetici", "baskan", "genel_sekreter"}
DB = Annotated[AsyncSession, Depends(get_db)]
Actor = Annotated[TokenPayload, Depends(get_current_user)]
Club = Annotated[uuid.UUID, Depends(get_club_id)]


def manager(user):
    if user.role not in MANAGERS:
        raise HTTPException(403, "Duyuru yönetimi yetkiniz yok.")


def out(item):
    return AnnouncementOut(
        **{
            key: getattr(item, key)
            for key in AnnouncementOut.model_fields
            if hasattr(item, key)
        },
        target_roles=sorted(a.role_code for a in item.audiences),
    )


async def find(db, club, item_id):
    item = (
        await db.execute(
            select(Announcement).where(
                Announcement.id == item_id,
                Announcement.club_id == club,
                Announcement.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Duyuru bulunamadı.")
    return item


@router.get("", response_model=AnnouncementList)
async def list_announcements(
    db: DB,
    user: Actor,
    club: Club,
    manage: bool = False,
    status: AnnouncementStatus | None = None,
    search: str | None = Query(None, max_length=200),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
):
    filters = [Announcement.club_id == club, Announcement.is_deleted.is_(False)]
    if manage:
        manager(user)
    else:
        today = datetime.now(ZoneInfo("Europe/Istanbul")).date()
        filters.extend(
            [
                Announcement.status == "yayinda",
                or_(Announcement.starts_on.is_(None), Announcement.starts_on <= today),
                or_(Announcement.ends_on.is_(None), Announcement.ends_on >= today),
                or_(
                    ~Announcement.audiences.any(),
                    Announcement.audiences.any(role_code=user.role),
                ),
            ]
        )
    if status:
        filters.append(Announcement.status == status)
    if search and search.strip():
        value = (
            search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        filters.append(
            or_(
                Announcement.title.ilike(f"%{value}%", escape="\\"),
                Announcement.body.ilike(f"%{value}%", escape="\\"),
            )
        )
    total = (
        await db.execute(select(func.count()).select_from(Announcement).where(*filters))
    ).scalar_one()
    items = (
        (
            await db.execute(
                select(Announcement)
                .where(*filters)
                .order_by(
                    Announcement.important.desc(),
                    Announcement.created_at.desc(),
                    Announcement.id,
                )
                .offset(skip)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return AnnouncementList(items=[out(item) for item in items], total=total)


@router.post("", response_model=AnnouncementOut, status_code=201)
async def create(
    data: AnnouncementInput, request: Request, db: DB, user: Actor, club: Club
):
    manager(user)
    item = Announcement(club_id=club, **data.model_dump(exclude={"target_roles"}))
    item.audiences = [
        AnnouncementAudience(role_code=role) for role in data.target_roles
    ]
    db.add(item)
    await db.flush()
    await log_action(
        db,
        action="announcement_created",
        resource_type="announcement",
        resource_id=str(item.id),
        club_id=club,
        user_id=uuid.UUID(user.sub),
        after=data.model_dump(mode="json"),
        request=request,
    )
    return out(item)


@router.put("/{item_id}", response_model=AnnouncementOut)
async def update(
    item_id: uuid.UUID,
    data: AnnouncementInput,
    request: Request,
    db: DB,
    user: Actor,
    club: Club,
):
    manager(user)
    item = await find(db, club, item_id)
    before = out(item).model_dump(mode="json")
    for key, value in data.model_dump(exclude={"target_roles"}).items():
        setattr(item, key, value)
    old = {a.role_code: a for a in item.audiences}
    item.audiences = [
        old.get(role) or AnnouncementAudience(role_code=role)
        for role in data.target_roles
    ]
    await db.flush()
    await db.refresh(item)
    await log_action(
        db,
        action="announcement_updated",
        resource_type="announcement",
        resource_id=str(item.id),
        club_id=club,
        user_id=uuid.UUID(user.sub),
        before=before,
        after=data.model_dump(mode="json"),
        request=request,
    )
    return out(item)


@router.delete("/{item_id}", status_code=204)
async def delete(item_id: uuid.UUID, request: Request, db: DB, user: Actor, club: Club):
    manager(user)
    item = await find(db, club, item_id)
    item.is_deleted = True
    await log_action(
        db,
        action="announcement_deleted",
        resource_type="announcement",
        resource_id=str(item.id),
        club_id=club,
        user_id=uuid.UUID(user.sub),
        request=request,
    )
    await db.flush()
    return Response(status_code=204)
