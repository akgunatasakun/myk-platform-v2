"""Equipment Core — ekipman envanteri ve bakım kayıtları.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-11

Değişiklikler (2 tablo):
  1. equipment                       — ekipman envanteri (Flask ekipmanlar)
  2. equipment_maintenance_records   — bakım geçmişi (Flask'ta yoktu — yeni)

Tasarım notları:
  - Flask zimmetli_kullanici (users FK) → assigned_person_id (persons FK).
    Zimmet kişiye yapılır, login hesabına değil.
  - status: aktif | bakimda | hasarli | hizmetdisi — CHECK constraint.
  - purchase_cost NUMERIC(12,2) CHECK >= 0 (0 değeri geçerli; bağış/devirde).
  - serial_no: tenant-scoped partial unique (aynı kulüpte aynı seri no olmaz).
  - equipment.last/next_maintenance_date: summary/cache;
    equipment_maintenance_records.next_maintenance_date kayıt sırasında güncellenir.
  - Maintenance cost CHECK >= 0.
  - Silme: is_deleted soft delete (her iki tabloda).

Flask bug düzeltmesi:
  Eski kodda rezervasyon kontrolü ('hasarli','bakim') kullanıyordu; doğru değer 'bakimda'.
  Sprint 6D (rezervasyon) doğru değerler: bakimda | hasarli | hizmetdisi.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    _u = UUID(as_uuid=True) if is_pg else sa.String(36)

    # ── 1. equipment ─────────────────────────────────────────────────────────────
    op.create_table(
        "equipment",
        sa.Column("id", _u, primary_key=True),
        sa.Column(
            "club_id", _u,
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("equipment_type", sa.Text(), nullable=True),
        sa.Column("serial_no", sa.Text(), nullable=True),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("purchase_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="aktif",
        ),
        sa.Column(
            "assigned_person_id", _u,
            sa.ForeignKey("persons.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_maintenance_date", sa.Date(), nullable=True),
        sa.Column("next_maintenance_date", sa.Date(), nullable=True),
        sa.Column("insurance_expiry_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('aktif','bakimda','hasarli','hizmetdisi')",
            name="ck_equipment_status",
        ),
        sa.CheckConstraint(
            "purchase_cost IS NULL OR purchase_cost >= 0",
            name="ck_equipment_purchase_cost_nonneg",
        ),
    )

    # İndeksler
    op.create_index("ix_equipment_club_id",      "equipment", ["club_id"])
    op.create_index("ix_equipment_club_status",  "equipment", ["club_id", "status"])
    op.create_index(
        "ix_equipment_club_next_maint",
        "equipment",
        ["club_id", "next_maintenance_date"],
    )
    op.create_index(
        "ix_equipment_club_insurance",
        "equipment",
        ["club_id", "insurance_expiry_date"],
    )
    op.create_index(
        "ix_equipment_assigned_person",
        "equipment",
        ["assigned_person_id"],
    )

    # Tenant-scoped partial unique: aynı kulüpte aynı seri no olamaz (silinmemişlerde)
    if is_pg:
        op.execute(
            """
            CREATE UNIQUE INDEX uq_equipment_club_serial_no
              ON equipment(club_id, serial_no)
             WHERE serial_no IS NOT NULL AND is_deleted = false
            """
        )

    # ── 2. equipment_maintenance_records ─────────────────────────────────────────
    op.create_table(
        "equipment_maintenance_records",
        sa.Column("id", _u, primary_key=True),
        sa.Column(
            "club_id", _u,
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "equipment_id", _u,
            sa.ForeignKey("equipment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("maintenance_date", sa.Date(), nullable=False),
        sa.Column("maintenance_type", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("performed_by", sa.Text(), nullable=True),
        sa.Column("next_maintenance_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "recorded_by_user_id", _u,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "cost IS NULL OR cost >= 0",
            name="ck_maintenance_cost_nonneg",
        ),
    )

    op.create_index(
        "ix_maint_club_equipment",
        "equipment_maintenance_records",
        ["club_id", "equipment_id"],
    )
    op.create_index(
        "ix_maint_equipment_date",
        "equipment_maintenance_records",
        ["equipment_id", "maintenance_date"],
    )

    # ── PostgreSQL: myk_app izinleri ──────────────────────────────────────────────
    if is_pg:
        op.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON equipment TO myk_app"
        )
        op.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE "
            "ON equipment_maintenance_records TO myk_app"
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    op.drop_index("ix_maint_equipment_date",   table_name="equipment_maintenance_records")
    op.drop_index("ix_maint_club_equipment",   table_name="equipment_maintenance_records")
    op.drop_table("equipment_maintenance_records")

    op.drop_index("ix_equipment_assigned_person", table_name="equipment")
    op.drop_index("ix_equipment_club_insurance",  table_name="equipment")
    op.drop_index("ix_equipment_club_next_maint", table_name="equipment")
    op.drop_index("ix_equipment_club_status",     table_name="equipment")
    op.drop_index("ix_equipment_club_id",         table_name="equipment")

    if is_pg:
        op.execute("DROP INDEX IF EXISTS uq_equipment_club_serial_no")

    op.drop_table("equipment")
