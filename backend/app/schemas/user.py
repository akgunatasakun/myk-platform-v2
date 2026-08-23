"""Kullanıcı hesabı yönetimi şemaları — Sprint 18."""
import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# Atanabilir roller (K1: User.role — JWT kaynağı)
USER_ROLES = Literal[
    "super_admin",
    "kulup_yonetici",
    "genel_sekreter",
    "baskan",
    "yk_uyesi",
    "muhasebe",
    "sportif_direktor",
    "basantrenor",
    "antrenor",
    "personel",
    "saglik_sorumlusu",
    "guvenlik_operasyon",
    "veli",
    "sporcu",
    "uye",
    "misafir",
]

# G8: Rol yükseltme kısıtı — hangi rol hangi rolleri atayabilir?
ASSIGNABLE_ROLES_BY_ROLE: dict[str, set[str]] = {
    "super_admin": set(USER_ROLES.__args__),  # type: ignore[attr-defined]
    "kulup_yonetici": {
        # kulup_yonetici başka kulup_yonetici oluşturabilir (P0-7: tek yönetici sorunu)
        "kulup_yonetici",
        "genel_sekreter", "baskan", "yk_uyesi", "muhasebe",
        "sportif_direktor", "basantrenor", "antrenor",
        "personel", "saglik_sorumlusu", "guvenlik_operasyon",
        "veli", "sporcu", "uye", "misafir",
        # super_admin hariç
    },
    "genel_sekreter": {
        "muhasebe", "personel", "veli", "sporcu", "uye", "misafir",
    },
}

# K1: sporcu/antrenor User rolü için Person bağlantısı zorunlu
ROLES_REQUIRING_PERSON = {"sporcu", "antrenor"}


class UserCreate(BaseModel):
    """Yönetici tarafından kullanıcı oluşturma."""
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=200)
    role: str = Field(..., description="Atanacak rol")
    person_id: Optional[uuid.UUID] = Field(
        None,
        description="Bağlanacak Person kaydı. sporcu/antrenor rolleri için zorunlu.",
    )

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: str) -> str:
        valid = set(USER_ROLES.__args__)  # type: ignore[attr-defined]
        if v not in valid:
            raise ValueError(f"Geçersiz rol: {v!r}. Geçerli roller: {sorted(valid)}")
        return v

    @model_validator(mode="after")
    def person_required_for_role(self) -> "UserCreate":
        if self.role in ROLES_REQUIRING_PERSON and self.person_id is None:
            raise ValueError(
                f"'{self.role}' rolü için person_id zorunludur."
            )
        return self


class UserUpdate(BaseModel):
    """Kullanıcı güncelleme — yalnızca sağlanan alanlar değişir."""
    role: Optional[str] = None
    is_active: Optional[bool] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=200)

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid = set(USER_ROLES.__args__)  # type: ignore[attr-defined]
        if v not in valid:
            raise ValueError(f"Geçersiz rol: {v!r}")
        return v


class UserOut(BaseModel):
    """Kullanıcı detay yanıtı."""
    id: uuid.UUID
    club_id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    is_deleted: bool
    person_id: Optional[uuid.UUID]
    must_change_password: bool
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListItem(BaseModel):
    """Kullanıcı listesi satırı — daha az alan."""
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    person_id: Optional[uuid.UUID]
    last_login_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListOut(BaseModel):
    """Sayfalı kullanıcı listesi."""
    items: list[UserListItem]
    total: int
    skip: int
    limit: int


class UserCreateResponse(UserOut):
    """Kullanıcı oluşturma yanıtı — geçici parolayı içerir (yalnızca bir kez)."""
    temp_password: str = Field(
        ...,
        description="Geçici parola — yalnızca bu yanıtta gösterilir, tekrar alınamaz.",
    )


class PasswordResetResponse(BaseModel):
    """Parola sıfırlama yanıtı — geçici parolayı içerir (yalnızca bir kez)."""
    user_id: uuid.UUID
    temp_password: str = Field(
        ...,
        description="Yeni geçici parola — yalnızca bu yanıtta gösterilir, tekrar alınamaz.",
    )
