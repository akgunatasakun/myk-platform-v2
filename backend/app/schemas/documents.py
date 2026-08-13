"""DMS Pydantic şemaları — Pydantic v2.

Tüm input şemaları extra="forbid" kullanır.
"""
import uuid
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict

DOCUMENT_TYPES = Literal[
    "prosedur", "talimati", "form", "el_kitabi", "egitim_materyali",
    "operasyonel", "sporcu_belgesi", "ekipman_belgesi", "diger"
]

CONTENT_STATUSES = Literal["tamamlandi", "taslak", "eksik", "placeholder", "bilinmiyor"]

REVISION_STATUSES = Literal["taslak", "incelemede", "onaylandi", "yayinda", "arsivlendi", "bloke"]

FILE_ROLES = Literal["source", "published", "attachment", "signed", "rendered", "other"]


# ── Category ──────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    name: str
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    club_id: uuid.UUID
    code: str
    name: str
    description: Optional[str] = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ── Document ──────────────────────────────────────────────────────────────────

class DocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    title: str
    document_type: DOCUMENT_TYPES
    content_status: CONTENT_STATUSES = "taslak"
    category_id: Optional[uuid.UUID] = None
    owner_type: Optional[str] = None
    owner_id: Optional[uuid.UUID] = None


class DocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Optional[str] = None
    title: Optional[str] = None
    document_type: Optional[DOCUMENT_TYPES] = None
    content_status: Optional[CONTENT_STATUSES] = None
    category_id: Optional[uuid.UUID] = None
    owner_type: Optional[str] = None
    owner_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    club_id: uuid.UUID
    category_id: Optional[uuid.UUID] = None
    code: str
    title: str
    document_type: str
    content_status: str
    owner_type: Optional[str] = None
    owner_id: Optional[uuid.UUID] = None
    current_revision_id: Optional[uuid.UUID] = None
    is_active: bool
    is_deleted: bool
    created_by_user_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


# ── RevisionFile ──────────────────────────────────────────────────────────────

class RevisionFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    revision_id: uuid.UUID
    file_role: str
    original_filename: str
    mime_type: str
    file_size: int
    sha256: str
    storage_bucket: str
    storage_key: str
    is_primary: bool
    created_at: datetime


# ── Revision ──────────────────────────────────────────────────────────────────

class RevisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_code: str
    revision_no: Optional[int] = None
    revision_date: Optional[date] = None
    status: REVISION_STATUSES = "taslak"
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    description: Optional[str] = None
    source: Optional[str] = None
    manifest_row_id: Optional[str] = None
    is_current: bool = False


class RevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    revision_code: str
    revision_no: Optional[int] = None
    revision_date: Optional[date] = None
    status: str
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    description: Optional[str] = None
    source: Optional[str] = None
    manifest_row_id: Optional[str] = None
    is_current: bool
    created_by_user_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class RevisionDetailOut(RevisionOut):
    files: List[RevisionFileOut] = []


# ── DocumentDetail ────────────────────────────────────────────────────────────

class DocumentDetailOut(DocumentOut):
    revisions: List[RevisionDetailOut] = []
