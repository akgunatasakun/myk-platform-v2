"""Persons ve person_roles tabloları

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── persons ────────────────────────────────────────────────────────────
    op.create_table(
        "persons",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("club_id", UUID(as_uuid=True), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("national_id", sa.String(20), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("emergency_contact_name", sa.String(200), nullable=True),
        sa.Column("emergency_contact_phone", sa.String(20), nullable=True),
        sa.Column("blood_type", sa.String(5), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_persons_club_id", "persons", ["club_id"])
    op.create_index("ix_persons_name", "persons", ["club_id", "last_name", "first_name"])
    op.create_index("ix_persons_email", "persons", ["email"])
    op.create_index("ix_persons_phone", "persons", ["phone"])

    # ── person_roles ───────────────────────────────────────────────────────
    op.create_table(
        "person_roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("person_id", UUID(as_uuid=True), nullable=False),
        sa.Column("role_code", sa.String(20), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_person_roles_person_id", "person_roles", ["person_id"])
    op.create_unique_constraint(
        "uq_person_roles_person_role", "person_roles", ["person_id", "role_code"]
    )

    # ── GRANT (PostgreSQL only) ────────────────────────────────────────────
    # SQLite'ta GRANT komutu yoktur; diyalekt koruması zorunludur.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON persons TO myk_app;")
        op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO myk_app;")
        op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON person_roles TO myk_app;")


def downgrade() -> None:
    op.drop_table("person_roles")
    op.drop_table("persons")
