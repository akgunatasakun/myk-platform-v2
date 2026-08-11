"""Equipment Pydantic şemaları — Pydantic v2.

Tüm input şemaları extra="forbid" kullanır.
Status değerleri: aktif | bakimda | hasarli | hizmetdisi
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

EQUIPMENT_STATUS = Literal["aktif", "bakimda", "hasarli", "hizmetdisi"]


# ── EquipmentCreate ───────────────────────────────────────────────────────────

class EquipmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    equipment_type: Optional[str] = None
    serial_no: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    purchase_date: Optional[date] = None
    purchase_cost: Optional[Decimal] = Field(default=None, ge=0)
    status: EQUIPMENT_STATUS = "aktif"
    assigned_person_id: Optional[uuid.UUID] = None
    last_maintenance_date: Optional[date] = None
    next_maintenance_date: Optional[date] = None
    insurance_expiry_date: Optional[date] = None
    notes: Optional[str] = None
    is_active: bool = True


# ── EquipmentUpdate ───────────────────────────────────────────────────────────

class EquipmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    equipment_type: Optional[str] = None
    serial_no: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    purchase_date: Optional[date] = None
    purchase_cost: Optional[Decimal] = Field(default=None, ge=0)
    status: Optional[EQUIPMENT_STATUS] = None
    assigned_person_id: Optional[uuid.UUID] = None
    last_maintenance_date: Optional[date] = None
    next_maintenance_date: Optional[date] = None
    insurance_expiry_date: Optional[date] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


# ── EquipmentOut ──────────────────────────────────────────────────────────────

class EquipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    club_id: uuid.UUID
    name: str
    equipment_type: Optional[str] = None
    serial_no: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    purchase_date: Optional[date] = None
    purchase_cost: Optional[Decimal] = None
    status: str
    assigned_person_id: Optional[uuid.UUID] = None
    assigned_person_name: Optional[str] = None   # computed — router'da doldurulur
    last_maintenance_date: Optional[date] = None
    next_maintenance_date: Optional[date] = None
    insurance_expiry_date: Optional[date] = None
    notes: Optional[str] = None
    is_active: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class EquipmentListOut(BaseModel):
    items: List[EquipmentOut]
    total: int
    skip: int
    limit: int


# ── MaintenanceDueOut — GET /equipment/maintenance-due ────────────────────────

class MaintenanceDueOut(EquipmentOut):
    """Bakım/sigorta uyarısı hesaplanmış alanlarla."""
    maintenance_due: bool = False
    maintenance_days_remaining: Optional[int] = None  # negatif = gecikti
    insurance_due: bool = False
    insurance_days_remaining: Optional[int] = None    # negatif = gecikti


# ── MaintenanceRecordCreate ───────────────────────────────────────────────────

class MaintenanceRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maintenance_date: date
    maintenance_type: Optional[str] = None
    description: Optional[str] = None
    cost: Optional[Decimal] = Field(default=None, ge=0)
    performed_by: Optional[str] = None
    next_maintenance_date: Optional[date] = None
    notes: Optional[str] = None


# ── MaintenanceRecordUpdate ───────────────────────────────────────────────────

class MaintenanceRecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maintenance_date: Optional[date] = None
    maintenance_type: Optional[str] = None
    description: Optional[str] = None
    cost: Optional[Decimal] = Field(default=None, ge=0)
    performed_by: Optional[str] = None
    next_maintenance_date: Optional[date] = None
    notes: Optional[str] = None


# ── MaintenanceRecordOut ──────────────────────────────────────────────────────

class MaintenanceRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    club_id: uuid.UUID
    equipment_id: uuid.UUID
    maintenance_date: date
    maintenance_type: Optional[str] = None
    description: Optional[str] = None
    cost: Optional[Decimal] = None
    performed_by: Optional[str] = None
    next_maintenance_date: Optional[date] = None
    notes: Optional[str] = None
    recorded_by_user_id: Optional[uuid.UUID] = None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class MaintenanceRecordListOut(BaseModel):
    items: List[MaintenanceRecordOut]
    total: int
