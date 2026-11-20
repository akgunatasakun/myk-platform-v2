"""Yenileme takibi hukuki belge durumunu değiştirmez; dönemler açıkça kaydedilir."""

import uuid
from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.documents import Document
from app.models.renewal import DocumentRenewal
from app.models.user import User
from app.schemas.auth import TokenPayload
from app.schemas.renewal import (
    RenewalChoice,
    RenewalClosure,
    RenewalInput,
    RenewalList,
    RenewalOut,
)

router = APIRouter(prefix="/renewals", tags=["renewals"])
MANAGERS = {"super_admin", "kulup_yonetici", "genel_sekreter"}
READERS = MANAGERS | {"baskan", "yk_uyesi", "muhasebe"}
DB = Annotated[AsyncSession, Depends(get_db)]
Club = Annotated[uuid.UUID, Depends(get_club_id)]


async def reader(user: Annotated[TokenPayload, Depends(get_current_user)]):
    if user.role not in READERS:
        raise HTTPException(403, "Yenileme takibine erişim yetkiniz yok.")
    return user


Actor = Annotated[TokenPayload, Depends(reader)]


def manager(user):
    if user.role not in MANAGERS:
        raise HTTPException(403, "Yenileme yönetimi yetkiniz yok.")


def today():
    return datetime.now(ZoneInfo("Europe/Istanbul")).date()


def state(row):
    if row.is_closed:
        return "kapali"
    if row.expires_on is None:
        return "eksik"
    days = (row.expires_on - today()).days
    return (
        "gecikti"
        if days < 0
        else "yaklasiyor"
        if days <= row.warning_days
        else "guncel"
    )


def query(club):
    return (
        select(DocumentRenewal, Document.code, Document.title, User.full_name)
        .join(
            Document,
            (Document.id == DocumentRenewal.document_id)
            & (Document.club_id == club)
            & Document.is_deleted.is_(False),
        )
        .outerjoin(
            User,
            (User.id == DocumentRenewal.responsible_user_id)
            & (User.club_id == club)
            & User.is_deleted.is_(False),
        )
        .where(DocumentRenewal.club_id == club)
    )


def out(row):
    r, code, title, name = row
    return RenewalOut(
        **{key: getattr(r, key) for key in RenewalOut.model_fields if hasattr(r, key)},
        document_code=code,
        document_title=title,
        responsible_name=name,
        days_remaining=(r.expires_on - today()).days if r.expires_on else None,
        state=state(r),
    )


async def find(db, club, item_id, lock=False):
    q = select(DocumentRenewal).where(
        DocumentRenewal.id == item_id,
        DocumentRenewal.club_id == club,
        select(Document.id)
        .where(
            Document.id == DocumentRenewal.document_id,
            Document.club_id == club,
            Document.is_deleted.is_(False),
        )
        .exists(),
    )
    if lock:
        q = q.with_for_update()
    item = (await db.execute(q)).scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Yenileme kaydı bulunamadı.")
    return item


async def validate(db, club, data):
    doc = (
        await db.execute(
            select(Document).where(
                Document.id == data.document_id,
                Document.club_id == club,
                Document.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "Belge bulunamadı.")
    if data.responsible_user_id:
        person = (
            await db.execute(
                select(User.id).where(
                    User.id == data.responsible_user_id,
                    User.club_id == club,
                    User.is_active.is_(True),
                    User.is_deleted.is_(False),
                    User.role.in_(READERS),
                )
            )
        ).scalar_one_or_none()
        if person is None:
            raise HTTPException(
                422,
                "Sorumlu, kulübün aktif yönetim veya muhasebe kullanıcılarından seçilmelidir.",
            )


@router.get("/documents", response_model=list[RenewalChoice])
async def documents(
    db: DB,
    user: Actor,
    club: Club,
    search: str = Query("", max_length=200),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    manager(user)
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    docs = (
        (
            await db.execute(
                select(Document)
                .where(
                    Document.club_id == club,
                    Document.is_deleted.is_(False),
                    or_(
                        Document.title.ilike(
                            "%" + escaped + "%",
                            escape="\\",
                        ),
                        Document.code.ilike(
                            "%" + escaped + "%",
                            escape="\\",
                        ),
                    ),
                )
                .order_by(Document.code, Document.id)
                .offset(skip)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [RenewalChoice(id=d.id, name=f"{d.code} — {d.title}") for d in docs]


@router.get("/responsibles", response_model=list[RenewalChoice])
async def responsibles(db: DB, user: Actor, club: Club):
    manager(user)
    users = (
        (
            await db.execute(
                select(User)
                .where(
                    User.club_id == club,
                    User.is_active.is_(True),
                    User.is_deleted.is_(False),
                    User.role.in_(READERS),
                )
                .order_by(User.full_name, User.id)
            )
        )
        .scalars()
        .all()
    )
    return [RenewalChoice(id=u.id, name=u.full_name) for u in users]


@router.get("", response_model=RenewalList)
async def listing(
    db: DB,
    user: Actor,
    club: Club,
    view: Literal["acik", "gecmis", "uyari", "eksik", "gecikti"] = "acik",
    kind: Literal["police", "sozlesme"] | None = None,
    search: str = Query("", max_length=200),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
):
    q = query(club).where(DocumentRenewal.is_closed.is_(view == "gecmis"))
    if kind:
        q = q.where(DocumentRenewal.kind == kind)
    if search.strip():
        escaped = (
            search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        q = q.where(
            or_(
                Document.title.ilike(f"%{escaped}%", escape="\\"),
                Document.code.ilike(f"%{escaped}%", escape="\\"),
                DocumentRenewal.reference_no.ilike(f"%{escaped}%", escape="\\"),
            )
        )
    if view == "uyari":
        days = (
            func.julianday(DocumentRenewal.expires_on) - func.julianday(today())
            if db.bind.dialect.name == "sqlite"
            else DocumentRenewal.expires_on - today()
        )
        q = q.where(
            or_(
                DocumentRenewal.expires_on.is_(None),
                days <= DocumentRenewal.warning_days,
            )
        )
    elif view == "eksik":
        q = q.where(DocumentRenewal.expires_on.is_(None))
    elif view == "gecikti":
        q = q.where(DocumentRenewal.expires_on < today())
    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()
    rows = (
        await db.execute(
            q.order_by(
                DocumentRenewal.expires_on.asc().nullsfirst(), DocumentRenewal.id
            )
            .offset(skip)
            .limit(limit)
        )
    ).all()
    return RenewalList(items=[out(row) for row in rows], total=total)


async def save(db, user, club, request, data, item=None, previous=None):
    await validate(db, club, data)
    document = (
        await db.execute(
            select(Document).where(
                Document.id == data.document_id, Document.club_id == club
            )
        )
    ).scalar_one()
    document.management_only = True
    before = (
        {k: str(getattr(item, k)) for k in RenewalInput.model_fields} if item else None
    )
    if item is None:
        item = DocumentRenewal(
            club_id=club,
            previous_id=previous.id if previous else None,
            **data.model_dump(),
        )
        db.add(item)
    else:
        for key, value in data.model_dump().items():
            setattr(item, key, value)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            409,
            "Bu belgenin açık bir yenileme dönemi zaten var. Mevcut kaydı düzenleyin.",
        ) from None
    await db.refresh(item)
    await log_action(
        db,
        action="renewal_recorded",
        resource_type="document_renewal",
        resource_id=str(item.id),
        club_id=club,
        user_id=uuid.UUID(user.sub),
        before=before,
        after=data.model_dump(mode="json"),
        request=request,
    )
    return out(
        (await db.execute(query(club).where(DocumentRenewal.id == item.id))).one()
    )


@router.post("", response_model=RenewalOut, status_code=201)
async def create(data: RenewalInput, request: Request, db: DB, user: Actor, club: Club):
    manager(user)
    return await save(db, user, club, request, data)


@router.put("/{item_id}", response_model=RenewalOut)
async def update(
    item_id: uuid.UUID,
    data: RenewalInput,
    request: Request,
    db: DB,
    user: Actor,
    club: Club,
):
    manager(user)
    item = await find(db, club, item_id, lock=True)
    if item.is_closed or data.document_id != item.document_id:
        raise HTTPException(409, "Geçmiş dönem veya bağlı belge değiştirilemez.")
    return await save(db, user, club, request, data, item=item)


@router.post("/{item_id}/renew", response_model=RenewalOut, status_code=201)
async def renew(
    item_id: uuid.UUID,
    data: RenewalInput,
    request: Request,
    db: DB,
    user: Actor,
    club: Club,
):
    manager(user)
    previous = await find(db, club, item_id, lock=True)
    if previous.is_closed or previous.document_id != data.document_id:
        raise HTTPException(409, "Bu dönem daha önce yenilenmiş veya belge değişmiş.")
    if data.starts_on is None or data.expires_on is None:
        raise HTTPException(
            422, "Yeni dönem için başlangıç ve bitiş tarihi gereklidir."
        )
    if previous.expires_on and (
        data.starts_on < previous.expires_on or data.expires_on <= previous.expires_on
    ):
        raise HTTPException(
            422,
            "Yeni dönem önceki bitiş tarihinden önce başlayamaz ve bitiş tarihi ileri olmalıdır.",
        )
    await validate(db, club, data)
    previous.is_closed = True
    await db.flush()
    return await save(db, user, club, request, data, previous=previous)


@router.patch("/{item_id}/closure", response_model=RenewalOut)
async def closure(
    item_id: uuid.UUID,
    data: RenewalClosure,
    request: Request,
    db: DB,
    user: Actor,
    club: Club,
):
    manager(user)
    item = await find(db, club, item_id, lock=True)
    if not data.is_closed:
        successor = (
            await db.execute(
                select(DocumentRenewal.id).where(
                    DocumentRenewal.club_id == club,
                    DocumentRenewal.previous_id == item.id,
                )
            )
        ).first()
        if successor:
            raise HTTPException(409, "Yenilenmiş eski dönem yeniden açılamaz.")
    item.is_closed = data.is_closed
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Belgenin başka bir açık dönemi var.") from None
    await db.refresh(item)
    await log_action(
        db,
        action="renewal_closed" if data.is_closed else "renewal_reopened",
        resource_type="document_renewal",
        resource_id=str(item.id),
        club_id=club,
        user_id=uuid.UUID(user.sub),
        request=request,
    )
    return out(
        (await db.execute(query(club).where(DocumentRenewal.id == item.id))).one()
    )
