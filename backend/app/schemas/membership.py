"""Üyelik başvurusu şemaları — Pydantic v2.

Güvenlik notu:
  signature_object_key ve pdf_object_key istemciye açılmaz.
  Bunun yerine has_signature, has_pdf, signature_url, pdf_url döner.
"""
import uuid
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, field_validator

GENDERS = ["erkek", "kadin", "belirtilmedi"]
BLOOD_TYPES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "0+", "0-"]
VALID_STATUSES = {"draft", "submitted", "approved", "rejected", "cancelled"}


# ── Oluşturma ─────────────────────────────────────────────────────────────────

class MembershipApplicationCreate(BaseModel):
    """Yeni başvuru — draft olarak oluşturulur.

    program_preference bu şemada YOK — tarihsel veri, yalnızca
    PublicApplicationCreate ve MembershipApplicationOut'ta bulunur.
    Admin draft oluştururken program tercihini belirlemez.
    """
    person_id: Optional[uuid.UUID] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_id: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    blood_type: Optional[str] = None
    sports_branch_id: Optional[uuid.UUID] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    consent_text_version: Optional[str] = None

    model_config = {"extra": "forbid"}

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in GENDERS:
            raise ValueError(f"Geçersiz cinsiyet: {v}. Geçerli: {GENDERS}")
        return v

    @field_validator("blood_type")
    @classmethod
    def validate_blood_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in BLOOD_TYPES:
            raise ValueError(f"Geçersiz kan grubu: {v}. Geçerli: {BLOOD_TYPES}")
        return v


# ── Güncelleme ────────────────────────────────────────────────────────────────

class MembershipApplicationUpdate(BaseModel):
    """Başvuru alanlarını güncelle (yalnızca draft/submitted durumunda)."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_id: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    blood_type: Optional[str] = None
    sports_branch_id: Optional[uuid.UUID] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    consent_text_version: Optional[str] = None

    model_config = {"extra": "forbid"}

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in GENDERS:
            raise ValueError(f"Geçersiz cinsiyet: {v}. Geçerli: {GENDERS}")
        return v

    @field_validator("blood_type")
    @classmethod
    def validate_blood_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in BLOOD_TYPES:
            raise ValueError(f"Geçersiz kan grubu: {v}. Geçerli: {BLOOD_TYPES}")
        return v


# ── Durum Geçişi ──────────────────────────────────────────────────────────────

class MembershipStatusTransition(BaseModel):
    """Durum değişikliği isteği."""
    to_status: str
    reason: Optional[str] = None   # ret/iptal gerekçesi

    model_config = {"extra": "forbid"}

    @field_validator("to_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Geçersiz durum: {v}. Geçerli: {sorted(VALID_STATUSES)}")
        return v


# ── Response ─────────────────────────────────────────────────────────────────

class MembershipApplicationOut(BaseModel):
    """Başvuru response — signature_object_key ve pdf_object_key dışarı verilmez."""
    id: uuid.UUID
    club_id: uuid.UUID
    person_id: Optional[uuid.UUID] = None
    application_number: Optional[str] = None
    status: str

    # Başvuru sahibi bilgileri
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_id: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    blood_type: Optional[str] = None
    sports_branch_id: Optional[uuid.UUID] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    program_preference: Optional[str] = None
    preferred_course_id: Optional[uuid.UUID] = None
    preferred_course_name: Optional[str] = None
    application_type: str = "membership"
    consent_text_version: Optional[str] = None
    consent_accepted_at: Optional[datetime] = None

    # PDF — object_key yok, yalnızca has_pdf + pdf_url
    has_pdf: bool = False
    pdf_url: Optional[str] = None
    pdf_generated_at: Optional[datetime] = None

    # İmza — object_key yok, yalnızca has_signature + signature_url
    has_signature: bool = False
    signature_url: Optional[str] = None
    signed_at: Optional[datetime] = None

    # Onay / ret / iptal
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    submitted_at: Optional[datetime] = None

    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_safe(
        cls,
        app: object,
        pdf_url: Optional[str] = None,
        signature_url: Optional[str] = None,
    ) -> "MembershipApplicationOut":
        """ORM nesnesinden MembershipApplicationOut oluştur.

        pdf_object_key ve signature_object_key dışarı verilmez.
        URL'ler çalışma zamanında pre-signed olarak inject edilir.
        """
        obj = cls.model_validate(app)
        obj.has_pdf = getattr(app, "pdf_object_key", None) is not None
        obj.has_signature = getattr(app, "signature_object_key", None) is not None
        obj.pdf_url = pdf_url
        obj.signature_url = signature_url
        return obj


class MembershipApplicationListOut(BaseModel):
    items: List[MembershipApplicationOut]
    total: int
    skip: int
    limit: int


# ── PDF / İmza Response ───────────────────────────────────────────────────────

class MembershipPdfOut(BaseModel):
    """PDF endpoint response — object_key dışarı verilmez."""
    has_pdf: bool
    pdf_url: Optional[str] = None
    expires_in: Optional[int] = None   # saniye
    generated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MembershipSignatureOut(BaseModel):
    """İmza endpoint response — object_key dışarı verilmez."""
    has_signature: bool
    signature_url: Optional[str] = None
    expires_in: Optional[int] = None
    signed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
