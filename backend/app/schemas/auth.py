"""Auth şemaları — Pydantic v2."""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class LoginRequest(BaseModel):
    club_slug: str = Field(..., min_length=1, max_length=50, description="Kulüp slug'ı")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # saniye
    must_change_password: bool = False  # True → frontend zorunlu parola değiştirme ekranına yönlendirir


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    """JWT payload şeması."""
    sub: str       # user_id (UUID string)
    club_id: str   # UUID string
    role: str
    exp: datetime
    iat: datetime
    iss: str = "myk-platform"
    aud: str = "myk-client"
    type: str = "access"

    @property
    def user_id(self) -> uuid.UUID:
        return uuid.UUID(self.sub)

    @property
    def club_uuid(self) -> uuid.UUID:
        return uuid.UUID(self.club_id)


class SetupRequest(BaseModel):
    """İlk kulüp + yönetici kurulumu."""
    club_name: str = Field(..., min_length=2, max_length=200)
    club_slug: str = Field(..., pattern=r"^[a-z0-9-]{2,50}$")
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=10, max_length=128)
    admin_full_name: str = Field(..., min_length=2, max_length=200)

    @field_validator("admin_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Parola en az bir büyük harf içermelidir.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Parola en az bir rakam içermelidir.")
        return v


class UserResponse(BaseModel):
    id: uuid.UUID
    club_id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    must_change_password: bool = False  # Person'dan hesaplanır; /auth/me endpoint'i doldurur

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    """Kimlik doğrulanmış kullanıcının kendi parolasını değiştirme isteği."""

    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Parola en az bir büyük harf içermelidir.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Parola en az bir rakam içermelidir.")
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Yeni parolalar eşleşmiyor.")
        return self
