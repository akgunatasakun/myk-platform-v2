"""Denetim kaydı (audit log) router — Sprint 19.

Yetki: yalnızca kulup_yonetici / super_admin.
GET /api/v1/audit-logs  — sayfalı liste, filtreli.
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_permission
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.audit import AuditLog
from app.schemas.auth import TokenPayload
from pydantic import BaseModel

router = APIRouter(prefix="/audit-logs", tags=["audit"])


# ── Şemalar ───────────────────────────────────────────────────────────────────

class AuditLogItem(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    action: str
    resource_type: str
    resource_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    success: bool
    error_detail: Optional[str]
    changes: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListOut(BaseModel):
    items: list[AuditLogItem]
    total: int
    skip: int
    limit: int


# ── GET /audit-logs ───────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=AuditLogListOut,
    summary="Denetim kayıtları (sayfalı, filtreli)",
)
async def list_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = Query(None, description="Aksiyon filtresi (ör. login_success)"),
    actor_user_id: Optional[uuid.UUID] = Query(None, description="Yapan kullanıcı ID"),
    resource_type: Optional[str] = Query(None, description="Kaynak tipi (ör. user, person)"),
    success: Optional[bool] = Query(None, description="Başarı durumu"),
    from_dt: Optional[datetime] = Query(None, alias="from", description="Başlangıç zamanı (ISO 8601)"),
    to_dt: Optional[datetime] = Query(None, alias="to", description="Bitiş zamanı (ISO 8601)"),
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("kullanici:read")),
) -> AuditLogListOut:
    where = [AuditLog.club_id == club_id]

    if action:
        where.append(AuditLog.action == action)
    if actor_user_id is not None:
        where.append(AuditLog.user_id == actor_user_id)
    if resource_type:
        where.append(AuditLog.resource_type == resource_type)
    if success is not None:
        where.append(AuditLog.success.is_(success))
    if from_dt is not None:
        where.append(AuditLog.created_at >= from_dt)
    if to_dt is not None:
        where.append(AuditLog.created_at <= to_dt)

    total_result = await db.execute(
        select(func.count()).select_from(AuditLog).where(*where)
    )
    total = total_result.scalar_one()

    rows_result = await db.execute(
        select(AuditLog)
        .where(*where)
        .order_by(AuditLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = rows_result.scalars().all()

    return AuditLogListOut(
        items=[AuditLogItem.model_validate(r) for r in rows],
        total=total,
        skip=skip,
        limit=limit,
    )
