"""
Tenant izolasyon middleware ve yardımcıları.

Kural: Bir kulübün kullanıcısı başka kulübün verisine HİÇBİR KOŞULDA erişemez.
Her DB sorgusu club_id filtresi içermelidir.
"""
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user
from app.schemas.auth import TokenPayload


async def get_club_id(
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> uuid.UUID:
    """Mevcut kullanıcının club_id'sini döndürür."""
    return uuid.UUID(current_user.club_id)


def assert_same_club(resource_club_id: uuid.UUID, requester_club_id: uuid.UUID) -> None:
    """Kaynak başka bir kulübe aitse 404 fırlat (varlığı ifşa etme)."""
    if resource_club_id != requester_club_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kaynak bulunamadı.",
        )
