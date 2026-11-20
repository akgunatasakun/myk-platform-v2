import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=240)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("title")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Sertifika adı boş olamaz.")
        return value.strip()


class CertificateCreate(DraftUpdate):
    enrollment_id: uuid.UUID


class CertificateIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    issued_on: date
    expires_on: date | None = None

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.expires_on is not None and self.expires_on < self.issued_on:
            raise ValueError("Geçerlilik tarihi düzenleme tarihinden önce olamaz.")
        return self


class CertificateRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("İptal gerekçesi boş olamaz.")
        return value.strip()


class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    enrollment_id: uuid.UUID
    course_id: uuid.UUID
    person_id: uuid.UUID
    title: str
    person_name: str
    course_name: str
    status: Literal["draft", "issued", "revoked"]
    state: Literal["draft", "issued", "expired", "revoked"]
    number: str | None
    issued_on: date | None
    expires_on: date | None
    notes: str | None = None
    revocation_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class CertificateList(BaseModel):
    items: list[CertificateOut]
    total: int
    skip: int
    limit: int


class EnrollmentOption(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    course_name: str
    person_name: str
