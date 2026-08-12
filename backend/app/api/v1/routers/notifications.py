"""Bildirim (Notification) API router.

Endpoint'ler:
  GET  /notifications              → son 50 event (unread önce, sonra read)
  GET  /notifications/unread-count → okunmamış badge sayısı
  POST /notifications/{id}/read   → tek event okundu işaretle

Yetkilendirme: tüm endpoint'ler `kulup:read` gerektirir.

MVP notu: acknowledged_at kulüp seviyesindedir — aynı bildirimi gören
tüm admin kullanıcılar için tek seferdir. Gelecekte per-user okuma
gerekirse ayrı bir tablo eklenir.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.events import DomainEvent
from app.schemas.auth import TokenPayload

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ── Şemalar ───────────────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id: uuid.UUID
    event_type: str
    aggregate_type: str
    aggregate_id: Optional[str] = None
    payload: Optional[dict] = None
    status: str
    acknowledged_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountOut(BaseModel):
    count: int


# ── Yardımcı ──────────────────────────────────────────────────────────────────

async def _get_event(
    event_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
) -> DomainEvent:
    result = await db.execute(
        select(DomainEvent).where(
            DomainEvent.id == event_id,
            DomainEvent.club_id == club_id,
        )
    )
    ev = result.scalar_one_or_none()
    if ev is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bildirim bulunamadı.",
        )
    return ev


# ── Endpoint'ler ──────────────────────────────────────────────────────────────

@router.get("", response_model=List[NotificationOut])
async def list_notifications(
    club_id: uuid.UUID = Depends(get_club_id),
    _current_user: TokenPayload = Depends(get_current_user),
    limit: int = Query(default=50, le=100),
    unread_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> List[NotificationOut]:
    """Son bildirimleri döndür.

    Sıralama: okunmamışlar önce (acknowledged_at IS NULL), sonra created_at DESC.
    unread_only=true ile yalnızca okunmamışlar filtrelenebilir.
    """
    stmt = (
        select(DomainEvent)
        .where(DomainEvent.club_id == club_id)
        .order_by(
            DomainEvent.acknowledged_at.is_(None).desc(),  # NULL önce
            DomainEvent.created_at.desc(),
        )
        .limit(limit)
    )
    if unread_only:
        stmt = stmt.where(DomainEvent.acknowledged_at.is_(None))

    result = await db.execute(stmt)
    events = result.scalars().all()
    return [NotificationOut.model_validate(e) for e in events]


@router.get("/unread-count", response_model=UnreadCountOut)
async def get_unread_count(
    club_id: uuid.UUID = Depends(get_club_id),
    _current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountOut:
    """Okunmamış bildirim sayısını döndür (AppShell badge)."""
    result = await db.execute(
        select(func.count(DomainEvent.id)).where(
            DomainEvent.club_id == club_id,
            DomainEvent.acknowledged_at.is_(None),
        )
    )
    count: int = result.scalar_one()
    return UnreadCountOut(count=count)


@router.post("/{event_id}/read", response_model=NotificationOut)
async def mark_as_read(
    event_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    _current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationOut:
    """Tek bildirimi okundu olarak işaretle."""
    ev = await _get_event(event_id, club_id, db)
    if ev.acknowledged_at is None:
        ev.acknowledged_at = datetime.now(tz=timezone.utc)
        await db.commit()
        await db.refresh(ev)
    return NotificationOut.model_validate(ev)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_as_read(
    club_id: uuid.UUID = Depends(get_club_id),
    _current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Tüm okunmamış bildirimleri okundu işaretle."""
    from sqlalchemy import update

    now = datetime.now(tz=timezone.utc)
    await db.execute(
        update(DomainEvent)
        .where(
            DomainEvent.club_id == club_id,
            DomainEvent.acknowledged_at.is_(None),
        )
        .values(acknowledged_at=now)
    )
    await db.commit()
