"""Equipment (Ekipman) modelleri — envanter ve bakım geçmişi.

İki model:
  Equipment                  — ekipman envanteri (Flask ekipmanlar)
  EquipmentMaintenanceRecord — bakım kayıtları (Flask'ta yoktu)

Tasarım:
  - assigned_person_id → persons.id (Flask zimmetli_kullanici users FK'sine değil)
  - status: aktif | bakimda | hasarli | hizmetdisi
  - equipment.last_maintenance_date / next_maintenance_date: hızlı listeleme için summary.
    Asıl kaynak: equipment_maintenance_records.
  - Bakım kaydedildiğinde service layer equipment summary'sini günceller.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.user import User


EQUIPMENT_STATUSES = ("aktif", "bakimda", "hasarli", "hizmetdisi")

# Rezerve edilemeyen durumlar (Sprint 6D rezervasyon için)
EQUIPMENT_NON_RESERVABLE = frozenset({"bakimda", "hasarli", "hizmetdisi"})


class Equipment(Base):
    """Ekipman envanteri.

    Flask 'ekipmanlar' tablosunun dönüştürülmüş karşılığı.
    """

    __tablename__ = "equipment"

    __table_args__ = (
        CheckConstraint(
            "status IN ('aktif','bakimda','hasarli','hizmetdisi')",
            name="ck_equipment_status",
        ),
        CheckConstraint(
            "purchase_cost IS NULL OR purchase_cost >= 0",
            name="ck_equipment_purchase_cost_nonneg",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    equipment_type: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    serial_no: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    purchase_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    purchase_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    status: Mapped[str] = mapped_column(Text(), nullable=False, default="aktif")
    assigned_person_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"), nullable=True
    )
    last_maintenance_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    next_maintenance_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    insurance_expiry_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # İlişkiler
    assigned_person: Mapped[Optional["Person"]] = relationship(
        foreign_keys=[assigned_person_id],
        lazy="select",
    )
    maintenance_records: Mapped[List["EquipmentMaintenanceRecord"]] = relationship(
        back_populates="equipment",
        cascade="all, delete-orphan",
        order_by="EquipmentMaintenanceRecord.maintenance_date.desc()",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<Equipment {self.name!r} status={self.status!r} "
            f"club={self.club_id!s:.8}>"
        )


class EquipmentMaintenanceRecord(Base):
    """Ekipman bakım kaydı.

    Flask'ta karşılığı yoktu — yeni domain.

    Bakım geçmişi normalize edilmiştir; equipment.last/next_maintenance_date
    alanları yalnızca hızlı listeleme için summary/cache olarak kullanılır.
    """

    __tablename__ = "equipment_maintenance_records"

    __table_args__ = (
        CheckConstraint(
            "cost IS NULL OR cost >= 0",
            name="ck_maintenance_cost_nonneg",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    maintenance_date: Mapped[date] = mapped_column(Date(), nullable=False)
    maintenance_type: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    performed_by: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    next_maintenance_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    recorded_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # İlişkiler
    equipment: Mapped["Equipment"] = relationship(
        back_populates="maintenance_records",
        lazy="select",
    )
    recorded_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[recorded_by_user_id],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<MaintenanceRecord equipment={self.equipment_id!s:.8} "
            f"date={self.maintenance_date}>"
        )
