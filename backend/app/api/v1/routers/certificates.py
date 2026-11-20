"""Kulüp sertifika kaydı. Düzenleme yetkili kullanıcı kararıdır; otomatik uygunluk kararı verilmez."""

import csv
import io
import uuid
from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.certificate import TrainingCertificate as Cert
from app.models.person import Person
from app.models.training import TrainingCourse, TrainingEnrollment
from app.schemas.auth import TokenPayload
from app.schemas.certificate import (
    CertificateCreate,
    CertificateIssue,
    CertificateList,
    CertificateOut,
    CertificateRevoke,
    DraftUpdate,
    EnrollmentOption,
)
from app.services.person_scope_service import get_own_person_ids
from app.services.training_scope_service import get_antrenor_course_ids

MANAGERS = {"super_admin", "kulup_yonetici", "genel_sekreter"}
READERS = MANAGERS | {
    "baskan",
    "yk_uyesi",
    "sportif_direktor",
    "basantrenor",
    "antrenor",
    "sporcu",
    "veli",
}
router = APIRouter(prefix="/certificates", tags=["certificates"])
DB = Annotated[AsyncSession, Depends(get_db)]
Club = Annotated[uuid.UUID, Depends(get_club_id)]


async def reader(user: Annotated[TokenPayload, Depends(get_current_user)]):
    if user.role not in READERS:
        raise HTTPException(403, "Sertifika kayıtlarına erişim yetkiniz yok.")
    return user


Actor = Annotated[TokenPayload, Depends(reader)]


def manager(user):
    if user.role not in MANAGERS:
        raise HTTPException(403, "Sertifika yönetimi yetkiniz yok.")


def now():
    return datetime.now(ZoneInfo("Europe/Istanbul"))


def query(club):
    return (
        select(Cert, TrainingEnrollment.course_id, TrainingEnrollment.person_id)
        .join(
            TrainingEnrollment,
            (TrainingEnrollment.id == Cert.enrollment_id)
            & (TrainingEnrollment.club_id == club),
        )
        .where(Cert.club_id == club, Cert.is_deleted.is_(False))
    )


async def scoped(db, club, user):
    q = query(club)
    if user.role in {"sporcu", "veli"}:
        ids = await get_own_person_ids(uuid.UUID(user.sub), club, db, user.role)
        q = q.where(TrainingEnrollment.person_id.in_(ids), Cert.status != "draft")
    elif user.role in {"antrenor", "basantrenor"}:
        ids = await get_antrenor_course_ids(uuid.UUID(user.sub), club, db)
        q = q.where(TrainingEnrollment.course_id.in_(ids))
    return q


def out(row, user):
    c, course_id, person_id = row
    values = {k: getattr(c, k) for k in CertificateOut.model_fields if hasattr(c, k)}
    values.update(
        course_id=course_id,
        person_id=person_id,
        state="expired"
        if c.status == "issued"
        and c.expires_on is not None
        and c.expires_on < now().date()
        else c.status,
    )
    if user.role not in MANAGERS:
        values["notes"] = None
    return CertificateOut(**values)


def filters(q, search, state, course_id, enrollment_id):
    if search:
        term = "%" + search.strip() + "%"
        q = q.where(
            or_(
                Cert.number.ilike(term),
                Cert.title.ilike(term),
                Cert.person_name.ilike(term),
                Cert.course_name.ilike(term),
            )
        )
    if state == "expired":
        q = q.where(Cert.status == "issued", Cert.expires_on < now().date())
    elif state == "issued":
        q = q.where(
            Cert.status == "issued",
            or_(Cert.expires_on.is_(None), Cert.expires_on >= now().date()),
        )
    elif state:
        q = q.where(Cert.status == state)
    if course_id:
        q = q.where(TrainingEnrollment.course_id == course_id)
    if enrollment_id:
        q = q.where(Cert.enrollment_id == enrollment_id)
    return q


State = Literal["draft", "issued", "expired", "revoked"]


@router.get("", response_model=CertificateList)
async def listing(
    db: DB,
    club: Club,
    user: Actor,
    search: str | None = Query(None, max_length=200),
    state: State | None = None,
    course_id: uuid.UUID | None = None,
    enrollment_id: uuid.UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    q = filters(await scoped(db, club, user), search, state, course_id, enrollment_id)
    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()
    rows = (
        await db.execute(
            q.order_by(Cert.created_at.desc(), Cert.id).offset(skip).limit(limit)
        )
    ).all()
    return CertificateList(
        items=[out(r, user) for r in rows], total=total, skip=skip, limit=limit
    )


def csv_cell(value):
    text = "" if value is None else str(value)
    return (
        "'" + text
        if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
        else text
    )


@router.get("/export")
async def export_csv(
    db: DB,
    club: Club,
    user: Actor,
    search: str | None = Query(None, max_length=200),
    state: State | None = None,
    course_id: uuid.UUID | None = None,
    enrollment_id: uuid.UUID | None = None,
):
    q = filters(await scoped(db, club, user), search, state, course_id, enrollment_id)
    rows = (
        await db.execute(q.order_by(Cert.created_at.desc(), Cert.id).limit(10001))
    ).all()
    if len(rows) > 10000:
        raise HTTPException(
            422, "Dışa aktarma için filtreyi daraltın (en fazla 10.000 kayıt)."
        )
    stream = io.StringIO()
    writer = csv.writer(stream, delimiter=";")
    writer.writerow(
        [
            "Numara",
            "Sporcu / Katılımcı",
            "Kurs",
            "Sertifika",
            "Durum",
            "Düzenleme",
            "Geçerlilik",
        ]
    )
    for row in rows:
        c = out(row, user)
        writer.writerow(
            [
                csv_cell(v)
                for v in [
                    c.number,
                    c.person_name,
                    c.course_name,
                    c.title,
                    c.state,
                    c.issued_on,
                    c.expires_on,
                ]
            ]
        )
    return Response(
        "\ufeff" + stream.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="myk-sertifikalar.csv"',
            "Cache-Control": "no-store",
        },
    )


async def enrollment(db, club, enrollment_id):
    row = (
        await db.execute(
            select(TrainingEnrollment, Person, TrainingCourse)
            .join(Person, Person.id == TrainingEnrollment.person_id)
            .join(TrainingCourse, TrainingCourse.id == TrainingEnrollment.course_id)
            .where(
                TrainingEnrollment.id == enrollment_id,
                TrainingEnrollment.club_id == club,
                TrainingEnrollment.is_deleted.is_(False),
                Person.club_id == club,
                Person.is_deleted.is_(False),
                TrainingCourse.club_id == club,
                TrainingCourse.is_deleted.is_(False),
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "Eğitim katılımcı kaydı bulunamadı.")
    if row[0].status not in {"active", "completed"}:
        raise HTTPException(409, "İptal edilmiş eğitim kaydına sertifika düzenlenemez.")
    return row


@router.get("/enrollment-options", response_model=list[EnrollmentOption])
async def options(
    db: DB,
    club: Club,
    user: Actor,
    search: str | None = Query(None, max_length=200),
    course_id: uuid.UUID | None = None,
    enrollment_id: uuid.UUID | None = None,
):
    manager(user)
    q = (
        select(TrainingEnrollment, Person, TrainingCourse)
        .join(Person, Person.id == TrainingEnrollment.person_id)
        .join(TrainingCourse, TrainingCourse.id == TrainingEnrollment.course_id)
        .where(
            TrainingEnrollment.club_id == club,
            TrainingEnrollment.is_deleted.is_(False),
            TrainingEnrollment.status.in_(["active", "completed"]),
            Person.club_id == club,
            Person.is_deleted.is_(False),
            TrainingCourse.club_id == club,
            TrainingCourse.is_deleted.is_(False),
            ~select(Cert.id)
            .where(
                Cert.club_id == club,
                Cert.enrollment_id == TrainingEnrollment.id,
                Cert.is_deleted.is_(False),
                Cert.status.in_(["draft", "issued"]),
            )
            .exists(),
        )
    )
    if search:
        term = "%" + search.strip() + "%"
        q = q.where(
            or_(
                (Person.first_name + " " + Person.last_name).ilike(term),
                TrainingCourse.name.ilike(term),
            )
        )
    if course_id:
        q = q.where(TrainingCourse.id == course_id)
    if enrollment_id:
        q = q.where(TrainingEnrollment.id == enrollment_id)
    rows = (
        await db.execute(
            q.order_by(
                TrainingEnrollment.enrolled_at.desc(), TrainingEnrollment.id
            ).limit(50)
        )
    ).all()
    return [
        EnrollmentOption(
            id=e.id,
            course_id=c.id,
            course_name=c.name,
            person_name=f"{p.first_name} {p.last_name}",
        )
        for e, p, c in rows
    ]


async def find(db, club, item_id):
    item = (
        await db.execute(
            select(Cert)
            .where(Cert.id == item_id, Cert.club_id == club, Cert.is_deleted.is_(False))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Sertifika kaydı bulunamadı.")
    return item


async def audit(db, club, user, request, item, action, before=None):
    await log_action(
        db,
        club_id=club,
        user_id=uuid.UUID(user.sub),
        request=request,
        resource_type="training_certificate",
        resource_id=str(item.id),
        action=action,
        before=before,
        after={
            "status": item.status,
            "number": item.number,
            "enrollment_id": str(item.enrollment_id),
        },
    )


async def output(db, club, user, item_id):
    row = (
        await db.execute((await scoped(db, club, user)).where(Cert.id == item_id))
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "Sertifika kaydı bulunamadı.")
    return out(row, user)


@router.get("/{item_id}", response_model=CertificateOut)
async def detail(item_id: uuid.UUID, db: DB, club: Club, user: Actor):
    return await output(db, club, user, item_id)


@router.post("", response_model=CertificateOut, status_code=201)
async def create(
    body: CertificateCreate, request: Request, db: DB, club: Club, user: Actor
):
    manager(user)
    e, p, c = await enrollment(db, club, body.enrollment_id)
    item = Cert(
        club_id=club,
        enrollment_id=e.id,
        title=body.title,
        notes=body.notes,
        person_name=f"{p.first_name} {p.last_name}",
        course_name=c.name,
        created_by_user_id=uuid.UUID(user.sub),
    )
    try:
        async with db.begin_nested():
            db.add(item)
            await db.flush()
    except IntegrityError:
        raise HTTPException(
            409, "Bu eğitim katılımcısı için açık bir sertifika kaydı zaten var."
        )
    await audit(db, club, user, request, item, "certificate_drafted")
    return await output(db, club, user, item.id)


@router.patch("/{item_id}", response_model=CertificateOut)
async def update(
    item_id: uuid.UUID,
    body: DraftUpdate,
    request: Request,
    db: DB,
    club: Club,
    user: Actor,
):
    manager(user)
    item = await find(db, club, item_id)
    if item.status != "draft":
        raise HTTPException(409, "Yalnız taslak kayıtlar düzenlenebilir.")
    before = {"title": item.title}
    item.title, item.notes = body.title, body.notes
    await db.flush()
    await db.refresh(item)
    await audit(db, club, user, request, item, "certificate_updated", before)
    return await output(db, club, user, item.id)


@router.post("/{item_id}/issue", response_model=CertificateOut)
async def issue(
    item_id: uuid.UUID,
    body: CertificateIssue,
    request: Request,
    db: DB,
    club: Club,
    user: Actor,
):
    manager(user)
    item = await find(db, club, item_id)
    if item.status != "draft":
        raise HTTPException(409, "Yalnız taslak sertifika düzenlenebilir.")
    if body.issued_on > now().date():
        raise HTTPException(422, "Düzenleme tarihi gelecekte olamaz.")
    e, p, c = await enrollment(db, club, item.enrollment_id)
    item.person_name, item.course_name = f"{p.first_name} {p.last_name}", c.name
    item.number = f"MYK-SRT-{body.issued_on.year}-{uuid.uuid4().hex[:12].upper()}"
    item.status, item.issued_on, item.expires_on = (
        "issued",
        body.issued_on,
        body.expires_on,
    )
    item.issued_by_user_id = uuid.UUID(user.sub)
    await db.flush()
    await db.refresh(item)
    await audit(db, club, user, request, item, "certificate_issued")
    return await output(db, club, user, item.id)


@router.post("/{item_id}/revoke", response_model=CertificateOut)
async def revoke(
    item_id: uuid.UUID,
    body: CertificateRevoke,
    request: Request,
    db: DB,
    club: Club,
    user: Actor,
):
    manager(user)
    item = await find(db, club, item_id)
    if item.status != "issued":
        raise HTTPException(409, "Yalnız düzenlenmiş sertifika iptal edilebilir.")
    item.status, item.revocation_reason = "revoked", body.reason
    item.revoked_at, item.revoked_by_user_id = now(), uuid.UUID(user.sub)
    await db.flush()
    await db.refresh(item)
    await audit(db, club, user, request, item, "certificate_revoked")
    return await output(db, club, user, item.id)


@router.delete("/{item_id}", status_code=204)
async def delete_draft(
    item_id: uuid.UUID, request: Request, db: DB, club: Club, user: Actor
):
    manager(user)
    item = await find(db, club, item_id)
    if item.status != "draft":
        raise HTTPException(
            409, "Düzenlenmiş sertifika silinemez; iptal işlemini kullanın."
        )
    item.is_deleted = True
    await db.flush()
    await audit(db, club, user, request, item, "certificate_draft_deleted")
