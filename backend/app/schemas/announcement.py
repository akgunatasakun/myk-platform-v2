import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.rbac import PERMISSIONS

AnnouncementStatus = Literal["taslak", "yayinda", "arsiv"]


class AnnouncementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    status: AnnouncementStatus = "taslak"
    important: bool = False
    starts_on: date | None = None
    ends_on: date | None = None
    target_roles: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("title", "body")
    @classmethod
    def clean_text(cls, value):
        if not value.strip():
            raise ValueError("Bu alan boş olamaz.")
        return value.strip()

    @field_validator("target_roles")
    @classmethod
    def valid_roles(cls, roles):
        if any(role not in PERMISSIONS for role in roles):
            raise ValueError("Geçersiz hedef rol.")
        return sorted(set(roles))

    @model_validator(mode="after")
    def valid_dates(self):
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValueError("Bitiş tarihi başlangıç tarihinden önce olamaz.")
        return self


class AnnouncementOut(AnnouncementInput):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AnnouncementList(BaseModel):
    items: list[AnnouncementOut]
    total: int
