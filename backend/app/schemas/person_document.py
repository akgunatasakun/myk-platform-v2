"""Kişisel evrak API şemaları — storage ayrıntıları özellikle dışarı verilmez."""
import json
import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class DeleteRequestData(BaseModel):
    """Belge üzerindeki silme isteği — DB'de JSON metin olarak saklanır."""
    model_config = ConfigDict(from_attributes=True)

    reason: str = ""
    requested_by_user_id: uuid.UUID
    status: str  # "pending" | "approved" | "rejected"
    created_at: datetime


class PersonDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    club_id: uuid.UUID
    subject_person_id: uuid.UUID
    guardian_link_id: Optional[uuid.UUID] = None
    document_type: str
    original_filename: str
    mime_type: str
    size_bytes: int
    uploaded_at: datetime
    valid_until: Optional[date] = None
    retain_until: Optional[date] = None
    review_status: str
    scan_status: str
    is_sensitive: bool
    is_deleted: bool = False
    supersedes_id: Optional[uuid.UUID] = None
    rejection_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    processing_basis: Optional[str] = None
    delete_request: Optional[DeleteRequestData] = None

    @field_validator("delete_request", mode="before")
    @classmethod
    def _parse_delete_request_json(cls, v: object) -> object:
        """DB'den gelen JSON metin string'ini dict'e çevirir."""
        if isinstance(v, str):
            return json.loads(v)
        return v


class RejectionBody(BaseModel):
    rejection_reason: str


class HealthDocumentSummaryOut(BaseModel):
    subject_person_id: uuid.UUID
    exists: bool
    valid_until: Optional[date] = None


class DeleteRequestBody(BaseModel):
    reason: str = ""


class DeleteRequestOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    requested_by_user_id: uuid.UUID
    reason: str
    created_at: datetime
    status: str  # "pending" | "approved" | "rejected"
