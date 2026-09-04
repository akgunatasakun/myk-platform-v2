"""PersonGuardian şemaları — Pydantic v2."""
import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class PersonMiniOut(BaseModel):
    """Veli kimlik özeti — PersonGuardianOut içinde kullanılır."""

    id: uuid.UUID
    first_name: str
    last_name: str
    member_number: Optional[str] = None
    phone: Optional[str] = None
    birth_date: Optional[date] = None

    model_config = {"from_attributes": True}


class PersonGuardianCreate(BaseModel):
    """Yeni veli bağlantısı oluşturma isteği."""

    guardian_person_id: uuid.UUID
    relationship_type: Optional[str] = Field(None, max_length=30)
    is_primary: bool = False
    can_pickup: bool = True
    can_receive_notifications: bool = True

    model_config = {"extra": "forbid"}


class PersonGuardianUpdate(BaseModel):
    """Veli bağlantısı güncelleme isteği — tüm alanlar opsiyonel."""

    relationship_type: Optional[str] = Field(None, max_length=30)
    is_primary: Optional[bool] = None
    can_pickup: Optional[bool] = None
    can_receive_notifications: Optional[bool] = None

    model_config = {"extra": "forbid"}


class PersonGuardianOut(BaseModel):
    """Veli bağlantısı API yanıtı."""

    id: uuid.UUID
    club_id: uuid.UUID
    athlete_person_id: uuid.UUID
    guardian_person_id: uuid.UUID
    relationship_type: Optional[str]
    is_primary: bool
    can_pickup: bool
    can_receive_notifications: bool
    created_at: datetime
    updated_at: datetime
    guardian: PersonMiniOut

    model_config = {"from_attributes": True}


class GuardianAthleteOut(BaseModel):
    """Velinin bağlı olduğu sporcu ilişkisi API yanıtı."""

    id: uuid.UUID
    club_id: uuid.UUID
    athlete_person_id: uuid.UUID
    guardian_person_id: uuid.UUID
    relationship_type: Optional[str]
    is_primary: bool
    can_pickup: bool
    can_receive_notifications: bool
    created_at: datetime
    updated_at: datetime
    athlete: PersonMiniOut

    model_config = {"from_attributes": True}
