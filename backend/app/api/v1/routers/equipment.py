"""Equipment router — ekipman envanteri ve bakım geçmişi.

Flask karşılıkları:
  GET  /api/ekipmanlar                 → GET  /equipment
  POST /api/ekipmanlar                 → POST /equipment
  GET  /api/ekipmanlar/:id             → GET  /equipment/{id}
  PUT  /api/ekipmanlar/:id             → PATCH /equipment/{id}
  GET  /api/ekipmanlar/bakim-gerekli   → GET  /equipment/maintenance-due
  (yok — yeni)                         → DELETE /equipment/{id}
  (yok — yeni)                         → GET  /equipment/{id}/maintenance
  (yok — yeni)                         → POST /equipment/{id}/maintenance
  (yok — yeni)                         → GET  /equipment/{id}/maintenance/{record_id}
  (yok — yeni)                         → PATCH /equipment/{id}/maintenance/{record_id}

RBAC:
  okuma   → ekipman:read
  yazma   → ekipman:write

Bakım uyarısı eşikleri (Flask ile aynı):
  bakım  : 14 gün
  sigorta: 30 gün
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.rbac import require_permission
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.equipment import Equipment, EquipmentMaintenanceRecord
from app.models.person import Person
from app.schemas.auth import TokenPayload
from app.schemas.equipment import (
    EquipmentCreate,
    EquipmentListOut,
    EquipmentOut,
    EquipmentUpdate,
    MaintenanceDueOut,
    MaintenanceRecordCreate,
    MaintenanceRecordListOut,
    MaintenanceRecordOut,
    MaintenanceRecordUpdate,
)

router = APIRouter(prefix="/equipment", tags=["equipment"])

# Uyarı eşikleri (Flask ile aynı)
MAINTENANCE_WARNING_DAYS = 14
INSURANCE_WARNING_DAYS = 30


# ─── Yardımcılar ─────────────────────────────────────────────────────────────

def _person_name(person: Optional[Person]) -> Optional[str]:
    if person is None:
        return None
    return f"{person.first_name} {person.last_name}".strip()


def _to_out(eq: Equipment) -> EquipmentOut:
    out = EquipmentOut.model_validate(eq)
    out.assigned_person_name = _person_name(eq.assigned_person)
    return out


def _to_maintenance_due(eq: Equipment, today: date) -> MaintenanceDueOut:
    base = _to_out(eq)

    maint_due = False
    maint_days: Optional[int] = None
    if eq.next_maintenance_date:
        delta = (eq.next_maintenance_date - today).days
        if delta <= MAINTENANCE_WARNING_DAYS:
            maint_due = True
            maint_days = delta

    ins_due = False
    ins_days: Optional[int] = None
    if eq.insurance_expiry_date:
        delta = (eq.insurance_expiry_date - today).days
        if delta <= INSURANCE_WARNING_DAYS:
            ins_due = True
            ins_days = delta

    return MaintenanceDueOut(
        **base.model_dump(),
        maintenance_due=maint_due,
        maintenance_days_remaining=maint_days,
        insurance_due=ins_due,
        insurance_days_remaining=ins_days,
    )


async def _get_equipment(
    equipment_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
) -> Equipment:
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Equipment)
        .options(selectinload(Equipment.assigned_person))
        .where(
            Equipment.id == equipment_id,
            Equipment.club_id == club_id,
            Equipment.is_deleted.is_(False),
        )
    )
    eq = result.scalar_one_or_none()
    if eq is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ekipman bulunamadı.",
        )
    return eq


async def _get_maintenance_record(
    record_id: uuid.UUID,
    equipment_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
) -> EquipmentMaintenanceRecord:
    result = await db.execute(
        select(EquipmentMaintenanceRecord).where(
            EquipmentMaintenanceRecord.id == record_id,
            EquipmentMaintenanceRecord.equipment_id == equipment_id,
            EquipmentMaintenanceRecord.club_id == club_id,
            EquipmentMaintenanceRecord.is_deleted.is_(False),
        )
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bakım kaydı bulunamadı.",
        )
    return rec


async def _validate_assigned_person(
    person_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """assigned_person_id bu kulübe ait mi?"""
    result = await db.execute(
        select(Person).where(
            Person.id == person_id,
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Belirtilen kişi bu kulüpte bulunamadı.",
        )


# ─── Ekipman listesi ──────────────────────────────────────────────────────────

@router.get("", response_model=EquipmentListOut)
async def list_equipment(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    equipment_type: Optional[str] = Query(default=None),
    assigned_person_id: Optional[uuid.UUID] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    club_id: uuid.UUID = Depends(get_club_id),
    _: None = Depends(require_permission("ekipman:read")),
    db: AsyncSession = Depends(get_db),
) -> EquipmentListOut:
    from sqlalchemy.orm import selectinload

    q = (
        select(Equipment)
        .options(selectinload(Equipment.assigned_person))
        .where(
            Equipment.club_id == club_id,
            Equipment.is_deleted.is_(False),
        )
    )
    if status_filter:
        q = q.where(Equipment.status == status_filter)
    if equipment_type:
        q = q.where(Equipment.equipment_type == equipment_type)
    if assigned_person_id is not None:
        q = q.where(Equipment.assigned_person_id == assigned_person_id)
    if is_active is not None:
        q = q.where(Equipment.is_active.is_(is_active))
    if search:
        like = f"%{search}%"
        q = q.where(
            Equipment.name.ilike(like)
            | Equipment.serial_no.ilike(like)
            | Equipment.brand.ilike(like)
        )

    total_result = await db.execute(
        select(func.count()).select_from(q.subquery())
    )
    total = total_result.scalar_one()

    result = await db.execute(
        q.order_by(Equipment.name.asc()).offset(skip).limit(limit)
    )
    items = result.scalars().all()

    return EquipmentListOut(
        items=[_to_out(e) for e in items],
        total=total,
        skip=skip,
        limit=limit,
    )


# ─── Bakım / sigorta uyarısı ─────────────────────────────────────────────────

@router.get("/maintenance-due", response_model=List[MaintenanceDueOut])
async def list_maintenance_due(
    club_id: uuid.UUID = Depends(get_club_id),
    _: None = Depends(require_permission("ekipman:read")),
    db: AsyncSession = Depends(get_db),
) -> List[MaintenanceDueOut]:
    """Flask /api/ekipmanlar/bakim-gerekli karşılığı.

    Eşikler:
      bakım   : 14 gün
      sigorta : 30 gün
    Geçmiş tarihler dahil (negatif days_remaining).
    """
    from sqlalchemy.orm import selectinload

    today = date.today()
    maint_cutoff = today + timedelta(days=MAINTENANCE_WARNING_DAYS)
    ins_cutoff = today + timedelta(days=INSURANCE_WARNING_DAYS)

    result = await db.execute(
        select(Equipment)
        .options(selectinload(Equipment.assigned_person))
        .where(
            Equipment.club_id == club_id,
            Equipment.is_deleted.is_(False),
            (
                (Equipment.next_maintenance_date <= maint_cutoff)
                | (Equipment.insurance_expiry_date <= ins_cutoff)
            ),
        )
        .order_by(Equipment.next_maintenance_date.asc().nulls_last())
    )
    items = result.scalars().all()
    return [_to_maintenance_due(e, today) for e in items]


# ─── Tekil ekipman ────────────────────────────────────────────────────────────

@router.get("/{equipment_id}", response_model=EquipmentOut)
async def get_equipment(
    equipment_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    _: None = Depends(require_permission("ekipman:read")),
    db: AsyncSession = Depends(get_db),
) -> EquipmentOut:
    eq = await _get_equipment(equipment_id, club_id, db)
    return _to_out(eq)


# ─── Ekipman oluştur ──────────────────────────────────────────────────────────

@router.post("", response_model=EquipmentOut, status_code=status.HTTP_201_CREATED)
async def create_equipment(
    body: EquipmentCreate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("ekipman:write")),
    db: AsyncSession = Depends(get_db),
) -> EquipmentOut:
    if body.assigned_person_id is not None:
        await _validate_assigned_person(body.assigned_person_id, club_id, db)

    eq = Equipment(
        id=uuid.uuid4(),
        club_id=club_id,
        name=body.name,
        equipment_type=body.equipment_type,
        serial_no=body.serial_no,
        brand=body.brand,
        model=body.model,
        purchase_date=body.purchase_date,
        purchase_cost=body.purchase_cost,
        status=body.status,
        assigned_person_id=body.assigned_person_id,
        last_maintenance_date=body.last_maintenance_date,
        next_maintenance_date=body.next_maintenance_date,
        insurance_expiry_date=body.insurance_expiry_date,
        notes=body.notes,
        is_active=body.is_active,
    )
    db.add(eq)
    await db.flush()
    await db.refresh(eq)

    await log_action(
        db,
        action="equipment_created",
        resource_type="equipment",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(eq.id),
        after={"name": eq.name, "status": eq.status},
        request=request,
    )

    if eq.assigned_person_id:
        await db.refresh(eq, ["assigned_person"])
    return _to_out(eq)


# ─── Ekipman güncelle ─────────────────────────────────────────────────────────

@router.patch("/{equipment_id}", response_model=EquipmentOut)
async def update_equipment(
    equipment_id: uuid.UUID,
    body: EquipmentUpdate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("ekipman:write")),
    db: AsyncSession = Depends(get_db),
) -> EquipmentOut:
    eq = await _get_equipment(equipment_id, club_id, db)
    update_data = body.model_dump(exclude_unset=True)

    if not update_data:
        return _to_out(eq)

    # assigned_person_id tenant kontrolü
    if "assigned_person_id" in update_data and update_data["assigned_person_id"] is not None:
        await _validate_assigned_person(update_data["assigned_person_id"], club_id, db)

    before = {k: str(getattr(eq, k, "")) for k in update_data}
    for field, value in update_data.items():
        setattr(eq, field, value)
    await db.flush()
    await db.refresh(eq)  # server-side updated_at için

    await log_action(
        db,
        action="equipment_updated",
        resource_type="equipment",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(eq.id),
        before=before,
        after={k: str(v) for k, v in update_data.items()},
        request=request,
    )

    if eq.assigned_person_id:
        await db.refresh(eq, ["assigned_person"])
    return _to_out(eq)


# ─── Ekipman sil (soft delete) ────────────────────────────────────────────────

@router.delete("/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_equipment(
    equipment_id: uuid.UUID,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("ekipman:write")),
    db: AsyncSession = Depends(get_db),
) -> None:
    eq = await _get_equipment(equipment_id, club_id, db)
    eq.is_deleted = True
    await db.flush()

    await log_action(
        db,
        action="equipment_deleted",
        resource_type="equipment",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(eq.id),
        request=request,
    )


# ─── Bakım kayıtları listesi ──────────────────────────────────────────────────

@router.get(
    "/{equipment_id}/maintenance",
    response_model=MaintenanceRecordListOut,
)
async def list_maintenance_records(
    equipment_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    club_id: uuid.UUID = Depends(get_club_id),
    _: None = Depends(require_permission("ekipman:read")),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceRecordListOut:
    # Önce ekipman tenant kontrolü
    await _get_equipment(equipment_id, club_id, db)

    q = select(EquipmentMaintenanceRecord).where(
        EquipmentMaintenanceRecord.equipment_id == equipment_id,
        EquipmentMaintenanceRecord.club_id == club_id,
        EquipmentMaintenanceRecord.is_deleted.is_(False),
    )

    total_result = await db.execute(
        select(func.count()).select_from(q.subquery())
    )
    total = total_result.scalar_one()

    result = await db.execute(
        q.order_by(EquipmentMaintenanceRecord.maintenance_date.desc())
        .offset(skip)
        .limit(limit)
    )
    items = result.scalars().all()

    return MaintenanceRecordListOut(
        items=[MaintenanceRecordOut.model_validate(r) for r in items],
        total=total,
    )


# ─── Bakım kaydı oluştur ─────────────────────────────────────────────────────

@router.post(
    "/{equipment_id}/maintenance",
    response_model=MaintenanceRecordOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_maintenance_record(
    equipment_id: uuid.UUID,
    body: MaintenanceRecordCreate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("ekipman:write")),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceRecordOut:
    eq = await _get_equipment(equipment_id, club_id, db)

    record = EquipmentMaintenanceRecord(
        id=uuid.uuid4(),
        club_id=club_id,
        equipment_id=equipment_id,
        maintenance_date=body.maintenance_date,
        maintenance_type=body.maintenance_type,
        description=body.description,
        cost=body.cost,
        performed_by=body.performed_by,
        next_maintenance_date=body.next_maintenance_date,
        notes=body.notes,
        recorded_by_user_id=uuid.UUID(current_user.sub),
    )
    db.add(record)

    # equipment summary güncellemesi
    eq.last_maintenance_date = body.maintenance_date
    if body.next_maintenance_date is not None:
        eq.next_maintenance_date = body.next_maintenance_date

    await db.flush()
    await db.refresh(record)
    await db.refresh(eq)  # updated_at için

    await log_action(
        db,
        action="maintenance_record_created",
        resource_type="equipment_maintenance",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(record.id),
        after={
            "equipment_id": str(equipment_id),
            "maintenance_date": str(body.maintenance_date),
            "cost": str(body.cost or ""),
        },
        request=request,
    )

    return MaintenanceRecordOut.model_validate(record)


# ─── Bakım kaydı detay ────────────────────────────────────────────────────────

@router.get(
    "/{equipment_id}/maintenance/{record_id}",
    response_model=MaintenanceRecordOut,
)
async def get_maintenance_record(
    equipment_id: uuid.UUID,
    record_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    _: None = Depends(require_permission("ekipman:read")),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceRecordOut:
    # Ekipman tenant kontrolü
    await _get_equipment(equipment_id, club_id, db)
    record = await _get_maintenance_record(record_id, equipment_id, club_id, db)
    return MaintenanceRecordOut.model_validate(record)


# ─── Bakım kaydı güncelle ─────────────────────────────────────────────────────

@router.patch(
    "/{equipment_id}/maintenance/{record_id}",
    response_model=MaintenanceRecordOut,
)
async def update_maintenance_record(
    equipment_id: uuid.UUID,
    record_id: uuid.UUID,
    body: MaintenanceRecordUpdate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("ekipman:write")),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceRecordOut:
    await _get_equipment(equipment_id, club_id, db)
    record = await _get_maintenance_record(record_id, equipment_id, club_id, db)

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return MaintenanceRecordOut.model_validate(record)

    before = {k: str(getattr(record, k, "")) for k in update_data}
    for field, value in update_data.items():
        setattr(record, field, value)
    await db.flush()
    await db.refresh(record)

    await log_action(
        db,
        action="maintenance_record_updated",
        resource_type="equipment_maintenance",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(record.id),
        before=before,
        after={k: str(v) for k, v in update_data.items()},
        request=request,
    )

    return MaintenanceRecordOut.model_validate(record)
