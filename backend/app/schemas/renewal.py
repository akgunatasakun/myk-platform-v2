import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RenewalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: uuid.UUID
    kind: Literal["police", "sozlesme"]
    reference_no: str | None = Field(default=None, max_length=128)
    starts_on: date | None = None
    expires_on: date | None = None
    warning_days: int = Field(default=30, ge=1, le=365)
    annual: bool = True
    responsible_user_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def valid_dates(self):
        if self.starts_on and self.expires_on and self.expires_on < self.starts_on:
            raise ValueError("Bitiş tarihi başlangıçtan önce olamaz.")
        return self


class RenewalOut(RenewalInput):
    id: uuid.UUID
    previous_id: uuid.UUID | None
    is_closed: bool
    document_code: str
    document_title: str
    responsible_name: str | None
    days_remaining: int | None
    state: Literal["eksik", "gecikti", "yaklasiyor", "guncel", "kapali"]
    created_at: datetime
    updated_at: datetime


class RenewalList(BaseModel):
    items: list[RenewalOut]
    total: int


class RenewalChoice(BaseModel):
    id: uuid.UUID
    name: str


class RenewalClosure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_closed: bool
