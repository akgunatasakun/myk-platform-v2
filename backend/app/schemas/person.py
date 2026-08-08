"""Kişi şemaları — Pydantic v2."""
import uuid
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, field_validator, model_serializer

PERSON_ROLE_CODES = ["sporcu", "uye", "veli", "antrenor", "personel", "misafir"]
BLOOD_TYPES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "0+", "0-"]
GENDERS = ["erkek", "kadin", "belirtilmedi"]


class PersonRoleOut(BaseModel):
    role_code: str
    assigned_at: datetime

    model_config = {"from_attributes": True}


class PersonBase(BaseModel):
    first_name: str
    last_name: str
    national_id: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    blood_type: Optional[str] = None
    notes: Optional[str] = None
    role_codes: List[str] = []

    model_config = {"extra": "forbid"}

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 1:
            raise ValueError("Ad en az 1 karakter olmalıdır.")
        if len(v) > 100:
            raise ValueError("Ad en fazla 100 karakter olabilir.")
        return v

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 1:
            raise ValueError("Soyad en az 1 karakter olmalıdır.")
        if len(v) > 100:
            raise ValueError("Soyad en fazla 100 karakter olabilir.")
        return v

    @field_validator("national_id")
    @classmethod
    def validate_national_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 20:
            raise ValueError("TC/Pasaport no en fazla 20 karakter olabilir.")
        return v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in GENDERS:
            raise ValueError(f"Cinsiyet şu değerlerden biri olmalıdır: {GENDERS}")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 20:
            raise ValueError("Telefon en fazla 20 karakter olabilir.")
        return v

    @field_validator("emergency_contact_name")
    @classmethod
    def validate_emergency_contact_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 200:
            raise ValueError("Acil kişi adı en fazla 200 karakter olabilir.")
        return v

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_contact_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 20:
            raise ValueError("Acil telefon en fazla 20 karakter olabilir.")
        return v

    @field_validator("blood_type")
    @classmethod
    def validate_blood_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in BLOOD_TYPES:
            raise ValueError(f"Kan grubu şu değerlerden biri olmalıdır: {BLOOD_TYPES}")
        return v

    @field_validator("role_codes")
    @classmethod
    def validate_role_codes(cls, v: List[str]) -> List[str]:
        for code in v:
            if code not in PERSON_ROLE_CODES:
                raise ValueError(f"Geçersiz rol kodu: {code}. Geçerli kodlar: {PERSON_ROLE_CODES}")
        return v


class PersonCreate(PersonBase):
    pass


class PersonUpdate(BaseModel):
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
    notes: Optional[str] = None
    role_codes: Optional[List[str]] = None
    is_active: Optional[bool] = None

    model_config = {"extra": "forbid"}

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) < 1:
                raise ValueError("Ad en az 1 karakter olmalıdır.")
            if len(v) > 100:
                raise ValueError("Ad en fazla 100 karakter olabilir.")
        return v

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) < 1:
                raise ValueError("Soyad en az 1 karakter olmalıdır.")
            if len(v) > 100:
                raise ValueError("Soyad en fazla 100 karakter olabilir.")
        return v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in GENDERS:
            raise ValueError(f"Cinsiyet şu değerlerden biri olmalıdır: {GENDERS}")
        return v

    @field_validator("blood_type")
    @classmethod
    def validate_blood_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in BLOOD_TYPES:
            raise ValueError(f"Kan grubu şu değerlerden biri olmalıdır: {BLOOD_TYPES}")
        return v

    @field_validator("role_codes")
    @classmethod
    def validate_role_codes(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            for code in v:
                if code not in PERSON_ROLE_CODES:
                    raise ValueError(f"Geçersiz rol kodu: {code}. Geçerli kodlar: {PERSON_ROLE_CODES}")
        return v


class PersonOut(BaseModel):
    id: uuid.UUID
    club_id: uuid.UUID
    first_name: str
    last_name: str
    national_id: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    blood_type: Optional[str] = None
    notes: Optional[str] = None
    member_number: Optional[str] = None   # üye numarası — onay sonrası atanır (MYK-YY-NNNN)
    # avatar_object_key kasıtlı olarak PersonOut'ta YOK — storage key iç altyapı bilgisi
    avatar_url: Optional[str] = None      # pre-signed URL, çalışma zamanında doldurulur
    has_avatar: bool = False              # avatar_object_key is not None
    is_active: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    roles: List[PersonRoleOut] = []
    role_codes: List[str] = []

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_masked(cls, person: object, mask: bool = False) -> "PersonOut":
        """ORM objesinden PersonOut oluştur; mask=True ise hassas alanları gizle.

        avatar_object_key PersonOut'ta yer almaz (storage key iç altyapı bilgisi).
        has_avatar ORM nesnesinden okunur ve PersonOut'a yazılır.
        """
        obj = cls.model_validate(person)
        # Computed fields
        obj.role_codes = [r.role_code for r in obj.roles]
        # getattr: ORM nesnesinin avatar_object_key'ini PersonOut'tan değil doğrudan okur
        obj.has_avatar = getattr(person, "avatar_object_key", None) is not None
        if mask:
            obj.national_id = "***" if obj.national_id else None
            obj.blood_type = "***" if obj.blood_type else None
        return obj


class PersonListOut(BaseModel):
    items: List[PersonOut]
    total: int
    skip: int
    limit: int


class PersonAvatarOut(BaseModel):
    """Avatar endpoint response şeması.

    avatar_object_key kasıtlı olarak dışarı verilmez.
    """
    has_avatar: bool
    avatar_url: Optional[str] = None
    expires_in: Optional[int] = None   # saniye; None ise avatar yok

    model_config = {"from_attributes": True}
