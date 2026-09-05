"""Kişisel evrak API şemaları — storage ayrıntıları özellikle dışarı verilmez."""
import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


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
    supersedes_id: Optional[uuid.UUID] = None
    rejection_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    processing_basis: Optional[str] = None


class RejectionBody(BaseModel):
    rejection_reason: str


class HealthDocumentSummaryOut(BaseModel):
    subject_person_id: uuid.UUID
    exists: bool
    valid_until: Optional[date] = None
