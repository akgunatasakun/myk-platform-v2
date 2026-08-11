"""Payments — gelir ve tahsilat kaydı.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-10

Değişiklikler (1 tablo):
  1. payments — ödeme/tahsilat kayıtları

Tasarım notları:
  - odemeler → payments: Flask kaynağından doğrudan dönüştürme.
  - person_id nullable: sporcu/üyeye bağlı olmayan kulüp genel tahsilatları için.
  - payment_type serbest TEXT: Flask davranışını korur; ileride vocabulary tablosuna geçilebilir.
  - status uygulama katmanında: pending | paid (DB TEXT, no CHECK constraint).
  - amount NUMERIC(12,2) CHECK > 0.
  - receipt_no benzersiz kısıtı YOK: kulüp bazlı unique ileride eklenebilir.
  - training_enrollments.payment_status: bu migration'da taşınmaz; cache olarak kalır.

Kimlik prensibi: kişi = persons.id; kaydeden = users.id.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    _u = UUID(as_uuid=True) if is_pg else sa.String(36)

    op.create_table(
        "payments",
        sa.Column("id", _u, primary_key=True),
        sa.Column(
            "club_id", _u,
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recorded_by_user_id", _u,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "person_id", _u,
            sa.ForeignKey("persons.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "amount",
            sa.Numeric(12, 2),
            nullable=False,
        ),
        sa.Column("payment_type", sa.Text(), nullable=True),
        sa.Column("payment_method", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_at", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("receipt_no", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
    )

    # ── İndeksler ─────────────────────────────────────────────────────────────
    op.create_index("ix_payments_club_status",   "payments", ["club_id", "status"])
    op.create_index("ix_payments_club_person",   "payments", ["club_id", "person_id"])
    op.create_index("ix_payments_club_due_date", "payments", ["club_id", "due_date"])
    op.create_index("ix_payments_club_paid_at",  "payments", ["club_id", "paid_at"])

    # ── PostgreSQL: myk_app izinleri ──────────────────────────────────────────
    if is_pg:
        op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON payments TO myk_app")


def downgrade() -> None:
    op.drop_index("ix_payments_club_paid_at",  table_name="payments")
    op.drop_index("ix_payments_club_due_date", table_name="payments")
    op.drop_index("ix_payments_club_person",   table_name="payments")
    op.drop_index("ix_payments_club_status",   table_name="payments")
    op.drop_table("payments")
