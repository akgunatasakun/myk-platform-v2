"""Settings router — Kulüp profili ve spor branşları yönetimi.

Endpoint listesi:
  GET    /settings/club              → kulüp bilgilerini getir
  PATCH  /settings/club              → kulüp bilgilerini güncelle

  GET    /settings/branches          → branş listesi (sort_order, name)
  POST   /settings/branches          → yeni branş
  PATCH  /settings/branches/{id}     → branş güncelle (name / is_active / sort_order)

RBAC:
  kulup:read   → GET endpoint'leri
  kulup:write  → PATCH / POST endpoint'leri
  (kulup_yonetici: kulup:* | super_admin: *)
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.rbac import require_permission
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.club import Club
from app.models.sports_branch import SportsBranch
from app.schemas.auth import TokenPayload
from app.schemas.settings import (
    BranchCreate,
    BranchOut,
    BranchUpdate,
    ClubOut,
    ClubSettingsUpdate,
)

router = APIRouter(prefix="/settings", tags=["settings"])


# ── Yardımcı ─────────────────────────────────────────────────────────────────

async def _get_club(club_id: uuid.UUID, db: AsyncSession) -> Club:
    result = await db.execute(select(Club).where(Club.id == club_id))
    club = result.scalar_one_or_none()
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kulüp bulunamadı.")
    return club


# ── Kulüp ayarları ────────────────────────────────────────────────────────────

@router.get("/club", response_model=ClubOut)
async def get_club_settings(
    club_id: uuid.UUID = Depends(get_club_id),
    _current_user: TokenPayload = Depends(get_current_user),
    _perm: None = Depends(require_permission("kulup:read")),
    db: AsyncSession = Depends(get_db),
) -> ClubOut:
    club = await _get_club(club_id, db)
    return ClubOut.from_club(club)


@router.patch("/club", response_model=ClubOut)
async def update_club_settings(
    body: ClubSettingsUpdate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _perm: None = Depends(require_permission("kulup:write")),
    db: AsyncSession = Depends(get_db),
) -> ClubOut:
    club = await _get_club(club_id, db)

    before = {"name": club.name, "settings": dict(club.settings or {})}

    # name → doğrudan kolon
    if body.name is not None:
        club.name = body.name.strip()

    # Diğer alanlar → settings JSON'a merge (mevcut anahtarları korur)
    merged = dict(club.settings or {})
    for field in ("phone", "email", "website", "address", "timezone", "currency"):
        val = getattr(body, field, None)
        if val is not None:
            merged[field] = val
    club.settings = merged

    await log_action(
        db,
        action="club_settings_updated",
        resource_type="club",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(club_id),
        before=before,
        after={"name": club.name, "settings": merged},
        request=request,
    )

    await db.commit()
    await db.refresh(club)
    return ClubOut.from_club(club)


# ── Spor branşları ────────────────────────────────────────────────────────────

@router.get("/branches", response_model=List[BranchOut])
async def list_branches(
    club_id: uuid.UUID = Depends(get_club_id),
    _current_user: TokenPayload = Depends(get_current_user),
    _perm: None = Depends(require_permission("kulup:read")),
    db: AsyncSession = Depends(get_db),
) -> List[BranchOut]:
    result = await db.execute(
        select(SportsBranch)
        .where(SportsBranch.club_id == club_id)
        .order_by(SportsBranch.sort_order, SportsBranch.name)
    )
    return result.scalars().all()


@router.post("/branches", response_model=BranchOut, status_code=status.HTTP_201_CREATED)
async def create_branch(
    body: BranchCreate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _perm: None = Depends(require_permission("kulup:write")),
    db: AsyncSession = Depends(get_db),
) -> BranchOut:
    branch = SportsBranch(
        id=uuid.uuid4(),
        club_id=club_id,
        name=body.name.strip(),
        is_active=True,
        sort_order=body.sort_order,
    )
    db.add(branch)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu isimde bir branş zaten mevcut.",
        )

    await log_action(
        db,
        action="sports_branch_created",
        resource_type="sports_branch",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(branch.id),
        after={"name": branch.name, "sort_order": branch.sort_order},
        request=request,
    )

    await db.commit()
    await db.refresh(branch)
    return branch


@router.patch("/branches/{branch_id}", response_model=BranchOut)
async def update_branch(
    branch_id: uuid.UUID,
    body: BranchUpdate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _perm: None = Depends(require_permission("kulup:write")),
    db: AsyncSession = Depends(get_db),
) -> BranchOut:
    result = await db.execute(
        select(SportsBranch).where(
            SportsBranch.id == branch_id,
            SportsBranch.club_id == club_id,
        )
    )
    branch = result.scalar_one_or_none()
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branş bulunamadı.")

    before = {
        "name": branch.name,
        "is_active": branch.is_active,
        "sort_order": branch.sort_order,
    }

    if body.name is not None:
        branch.name = body.name.strip()
    if body.is_active is not None:
        branch.is_active = body.is_active
    if body.sort_order is not None:
        branch.sort_order = body.sort_order

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu isimde bir branş zaten mevcut.",
        )

    await log_action(
        db,
        action="sports_branch_updated",
        resource_type="sports_branch",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(branch_id),
        before=before,
        after={
            "name": branch.name,
            "is_active": branch.is_active,
            "sort_order": branch.sort_order,
        },
        request=request,
    )

    await db.commit()
    await db.refresh(branch)
    return branch
