"""Üyelik başvurusu tam şema + application_counters tablosu

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-04

Değişiklikler:
  - membership_applications: eksik kolonlar eklendi, person_id nullable yapıldı
  - application_counters: yarış koşuluna dayanıklı numara üretimi için
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. membership_applications — person_id nullable ───────────────────
    # SQLite ALTER COLUMN DROP NOT NULL desteklemez; diyalekt koruması
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column("membership_applications", "person_id", nullable=True)

    # ── 2. membership_applications — yeni kolonlar ────────────────────────
    op.add_column("membership_applications",
        sa.Column("application_number", sa.String(30), nullable=True))
    op.add_column("membership_applications",
        sa.Column("first_name", sa.String(100), nullable=True))
    op.add_column("membership_applications",
        sa.Column("last_name", sa.String(100), nullable=True))
    op.add_column("membership_applications",
        sa.Column("national_id", sa.String(20), nullable=True))
    op.add_column("membership_applications",
        sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("membership_applications",
        sa.Column("gender", sa.String(10), nullable=True))
    op.add_column("membership_applications",
        sa.Column("phone", sa.String(20), nullable=True))
    op.add_column("membership_applications",
        sa.Column("email", sa.String(254), nullable=True))
    op.add_column("membership_applications",
        sa.Column("address", sa.Text(), nullable=True))
    op.add_column("membership_applications",
        sa.Column("emergency_contact_name", sa.String(200), nullable=True))
    op.add_column("membership_applications",
        sa.Column("emergency_contact_phone", sa.String(20), nullable=True))
    op.add_column("membership_applications",
        sa.Column("blood_type", sa.String(5), nullable=True))
    op.add_column("membership_applications",
        sa.Column("sports_branch_id", UUID(as_uuid=True), nullable=True))
    op.add_column("membership_applications",
        sa.Column("guardian_name", sa.String(200), nullable=True))
    op.add_column("membership_applications",
        sa.Column("guardian_phone", sa.String(20), nullable=True))
    op.add_column("membership_applications",
        sa.Column("consent_text_version", sa.String(20), nullable=True))
    op.add_column("membership_applications",
        sa.Column("consent_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("membership_applications",
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("membership_applications",
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("membership_applications",
        sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("membership_applications",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("membership_applications",
        sa.Column("cancellation_reason", sa.Text(), nullable=True))
    op.add_column("membership_applications",
        sa.Column("is_deleted", sa.Boolean(), nullable=False,
                  server_default="false"))
    op.add_column("membership_applications",
        sa.Column("pdf_generated_at", sa.DateTime(timezone=True), nullable=True))

    # unique constraint: application_number kulüp içinde unique
    if bind.dialect.name == "postgresql":
        op.create_unique_constraint(
            "uq_membership_applications_number",
            "membership_applications",
            ["club_id", "application_number"],
        )
        # sports_branch_id FK
        op.create_foreign_key(
            "fk_membership_applications_branch",
            "membership_applications",
            "sports_branches",
            ["sports_branch_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_index(
        "ix_membership_applications_number",
        "membership_applications",
        ["club_id", "application_number"],
    )

    # ── 3. application_counters ────────────────────────────────────────────
    # Yarış koşuluna dayanıklı sıra numarası üretimi için.
    # INSERT ... ON CONFLICT DO UPDATE ile atomic increment sağlanır.
    op.create_table(
        "application_counters",
        sa.Column("club_id", UUID(as_uuid=True), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("club_id", "year", name="pk_application_counters"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
    )

    # ── GRANT (PostgreSQL only) ────────────────────────────────────────────
    if bind.dialect.name == "postgresql":
        op.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON application_counters TO myk_app;"
        )



    # Eski Sprint 3.1 uyumluluk kolonu artık zorunlu değildir.
    op.alter_column(
        "membership_applications",
        "applicant_name",
        existing_type=sa.String(),
        nullable=True,
    )

def downgrade() -> None:
    op.drop_table("application_counters")

    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint(
            "fk_membership_applications_branch", "membership_applications",
            type_="foreignkey"
        )
        op.drop_constraint(
            "uq_membership_applications_number", "membership_applications",
            type_="unique"
        )
    op.drop_index("ix_membership_applications_number", "membership_applications")

    # Eklenen kolonları kaldır
    for col in [
        "application_number", "first_name", "last_name", "national_id",
        "birth_date", "gender", "phone", "email", "address",
        "emergency_contact_name", "emergency_contact_phone", "blood_type",
        "sports_branch_id", "guardian_name", "guardian_phone",
        "consent_text_version", "consent_accepted_at", "submitted_at",
        "rejected_at", "rejection_reason", "cancelled_at",
        "cancellation_reason", "is_deleted", "pdf_generated_at",
    ]:
        op.drop_column("membership_applications", col)

    if op.get_bind().dialect.name == "postgresql":
        op.alter_column("membership_applications", "person_id", nullable=False)
