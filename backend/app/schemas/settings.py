"""Settings domain schema'ları — Kulüp profili ve spor branşları."""
import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


# ── Club ─────────────────────────────────────────────────────────────────────

class ClubOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    is_active: bool
    # settings JSON'dan açılan alanlar
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    timezone: str = "Europe/Istanbul"
    currency: str = "TRY"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_club(cls, club: object) -> "ClubOut":
        s: dict = club.settings or {}  # type: ignore[union-attr]
        return cls(
            id=club.id,  # type: ignore[attr-defined]
            name=club.name,  # type: ignore[attr-defined]
            slug=club.slug,  # type: ignore[attr-defined]
            plan=club.plan,  # type: ignore[attr-defined]
            is_active=club.is_active,  # type: ignore[attr-defined]
            phone=s.get("phone"),
            email=s.get("email"),
            website=s.get("website"),
            address=s.get("address"),
            timezone=s.get("timezone", "Europe/Istanbul"),
            currency=s.get("currency", "TRY"),
            created_at=club.created_at,  # type: ignore[attr-defined]
            updated_at=club.updated_at,  # type: ignore[attr-defined]
        )


class ClubSettingsUpdate(BaseModel):
    """PATCH /settings/club için whitelist edilmiş alanlar.

    extra=forbid: tanımlanmamış alanlar 422 döndürür; settings JSON'unu
    doğrudan patch etmeyi engeller.
    """
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[Literal["TRY", "EUR", "USD"]] = None

    model_config = {"extra": "forbid"}


# ── SportsBranch ─────────────────────────────────────────────────────────────

class BranchOut(BaseModel):
    id: uuid.UUID
    club_id: uuid.UUID
    name: str
    is_active: bool
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class BranchCreate(BaseModel):
    name: str
    sort_order: int = 0

    model_config = {"extra": "forbid"}


class BranchUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None

    model_config = {"extra": "forbid"}
