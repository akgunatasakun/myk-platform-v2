"""Audit log servisi — tüm değiştirici işlemler buraya yazılır."""
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def log_action(
    db: AsyncSession,
    *,
    action: str,
    resource_type: str,
    club_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    resource_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    request: Request | None = None,
    success: bool = True,
    error_detail: str | None = None,
) -> None:
    """
    Audit log kaydı oluştur.

    Hassas alanlar (tc_no, kan_grubu, vb.) bu fonksiyona GEÇİRİLMEMELİDİR.
    Çağıran servis maskelemeyi yapmaktan sorumludur.
    """
    ip = None
    user_agent = None
    if request:
        ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

    changes = None
    if before is not None or after is not None:
        changes = {}
        if before is not None:
            changes["before"] = before
        if after is not None:
            changes["after"] = after

    entry = AuditLog(
        club_id=club_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        changes=changes,
        ip_address=ip,
        user_agent=user_agent,
        success=success,
        error_detail=error_detail,
    )
    db.add(entry)
    # commit çağıran katman (get_db bağımlılığı) tarafından yapılır
