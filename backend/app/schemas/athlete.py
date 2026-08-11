"""Sporcu profil şemaları — Pydantic v2.

AthleteProfile, Person'ın 1:1 uzantısıdır.
Liste/detay endpoint'leri kişisel bilgileri Person'dan, sporcu bilgilerini
AthleteProfile'dan birleştiren composite DTO döndürür.

Hassas alanlar (RBAC maskeleme — muhasebe, personel, antrenor, basantrenor):
  allergies, special_conditions, health_report_expiry_date
"""
import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, field_validator

ATHLETE_LEVELS = ["baslangic", "orta", "ileri", "elit"]

# Belge durumu hesaplaması için runtime yardımcısı
DocumentStatus = Literal["gecerli", "yaklasan", "dolmus", "eksik"]


def _doc_status(expiry: Optional[date]) -> DocumentStatus:
    """Tarih → belge durumu (runtime; DB'de saklanmaz)."""
    from datetime import date as _date, timedelta
    if expiry is None:
        return "eksik"
    today = _date.today()
    if expiry < today:
        return "dolmus"
    if expiry <= today + timedelta(days=30):
        return "yaklasan"
    return "gecerli"


# ── Input Şemaları ────────────────────────────────────────────────────────────

class AthleteProfileCreate(BaseModel):
    sports_branch_id: Optional[uuid.UUID] = None
    class_name: Optional[str] = None
    level: Optional[str] = "baslangic"

    license_no: Optional[str] = None
    license_expiry_date: Optional[date] = None
    visa_expiry_date: Optional[date] = None

    health_report_expiry_date: Optional[date] = None
    swimming_qualified: bool = False

    allergies: Optional[str] = None
    special_conditions: Optional[str] = None

    kvkk_consent: bool = False
    kvkk_text_version: Optional[str] = None
    photo_video_consent: bool = False

    model_config = {"extra": "forbid"}

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ATHLETE_LEVELS:
            raise ValueError(f"Seviye şunlardan biri olmalıdır: {ATHLETE_LEVELS}")
        return v


class AthleteProfileUpdate(BaseModel):
    sports_branch_id: Optional[uuid.UUID] = None
    class_name: Optional[str] = None
    level: Optional[str] = None

    license_no: Optional[str] = None
    license_expiry_date: Optional[date] = None
    visa_expiry_date: Optional[date] = None

    health_report_expiry_date: Optional[date] = None
    swimming_qualified: Optional[bool] = None

    allergies: Optional[str] = None
    special_conditions: Optional[str] = None

    kvkk_consent: Optional[bool] = None
    kvkk_text_version: Optional[str] = None
    photo_video_consent: Optional[bool] = None

    model_config = {"extra": "forbid"}

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ATHLETE_LEVELS:
            raise ValueError(f"Seviye şunlardan biri olmalıdır: {ATHLETE_LEVELS}")
        return v


# ── Output Şemaları ────────────────────────────────────────────────────────────

class AthleteProfileOut(BaseModel):
    """Sadece AthleteProfile alanları — PersonOut içinde kullanılır."""
    sports_branch_id: Optional[uuid.UUID] = None
    sports_branch_name: Optional[str] = None
    class_name: Optional[str] = None
    level: Optional[str] = None

    license_no: Optional[str] = None
    license_expiry_date: Optional[date] = None
    license_status: DocumentStatus = "eksik"

    visa_expiry_date: Optional[date] = None
    visa_status: DocumentStatus = "eksik"

    health_report_expiry_date: Optional[date] = None
    health_status: DocumentStatus = "eksik"
    swimming_qualified: bool = False

    allergies: Optional[str] = None
    special_conditions: Optional[str] = None

    kvkk_consent: bool = False
    kvkk_consent_at: Optional[datetime] = None
    kvkk_text_version: Optional[str] = None
    photo_video_consent: bool = False

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, profile: object, mask: bool = False) -> "AthleteProfileOut":
        from app.models.athlete_profile import AthleteProfile as _AP
        p: _AP = profile  # type: ignore[assignment]
        obj = cls(
            sports_branch_id=p.sports_branch_id,
            sports_branch_name=p.sports_branch.name if p.sports_branch else None,
            class_name=p.class_name,
            level=p.level,
            license_no=p.license_no,
            license_expiry_date=p.license_expiry_date,
            license_status=_doc_status(p.license_expiry_date),
            visa_expiry_date=p.visa_expiry_date,
            visa_status=_doc_status(p.visa_expiry_date),
            health_report_expiry_date=None if mask else p.health_report_expiry_date,
            health_status="eksik" if mask else _doc_status(p.health_report_expiry_date),
            swimming_qualified=p.swimming_qualified,
            allergies=None if mask else p.allergies,
            special_conditions=None if mask else p.special_conditions,
            kvkk_consent=p.kvkk_consent,
            kvkk_consent_at=p.kvkk_consent_at,
            kvkk_text_version=p.kvkk_text_version,
            photo_video_consent=p.photo_video_consent,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        return obj


class AthleteListItem(BaseModel):
    """Sporcu listesi satırı — Person + AthleteProfile birleşik DTO."""
    person_id: uuid.UUID
    first_name: str
    last_name: str
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    member_number: Optional[str] = None
    is_active: bool

    # AthleteProfile alanları (profil yoksa None)
    sports_branch_name: Optional[str] = None
    class_name: Optional[str] = None
    level: Optional[str] = None

    license_no: Optional[str] = None
    license_expiry_date: Optional[date] = None
    license_status: DocumentStatus = "eksik"

    visa_expiry_date: Optional[date] = None
    visa_status: DocumentStatus = "eksik"

    health_report_expiry_date: Optional[date] = None
    health_status: DocumentStatus = "eksik"

    swimming_qualified: bool = False
    kvkk_consent: bool = False
    photo_video_consent: bool = False

    has_profile: bool = False

    model_config = {"from_attributes": True}


class AthleteListOut(BaseModel):
    items: list[AthleteListItem]
    total: int
    skip: int
    limit: int


class AthleteAlertItem(BaseModel):
    """Bitiş tarihi geçmiş/yaklaşan veya eksik belgesi olan sporcu."""
    person_id: uuid.UUID
    first_name: str
    last_name: str
    class_name: Optional[str] = None

    license_expiry_date: Optional[date] = None
    license_status: DocumentStatus = "eksik"

    visa_expiry_date: Optional[date] = None
    visa_status: DocumentStatus = "eksik"

    health_report_expiry_date: Optional[date] = None
    health_status: DocumentStatus = "eksik"

    kvkk_consent: bool = False

    alerts: list[str] = []   # İnsan okunabilir uyarı listesi

    model_config = {"from_attributes": True}
