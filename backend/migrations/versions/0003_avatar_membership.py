"""Avatar, branşlar ve üyelik başvurusu tabloları

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Seed verisi — OQ-02 kararı (dinamik branş tablosu)
SEED_BRANCHES = [
    "Yelken",
    "Optimist",
    "ILCA",
    "420",
    "470",
    "Wingfoil",
    "Windsurf",
    "Kitesurf",
    "Kano",
]


def upgrade() -> None:
    # ── 1. persons: avatar_url → avatar_object_key ─────────────────────────
    op.drop_column("persons", "avatar_url")
    op.add_column(
        "persons",
        sa.Column("avatar_object_key", sa.String(500), nullable=True),
    )

    # ── 2. sports_branches ─────────────────────────────────────────────────
    op.create_table(
        "sports_branches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("club_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sports_branches_club_id", "sports_branches", ["club_id"])
    op.create_unique_constraint(
        "uq_sports_branches_name", "sports_branches", ["club_id", "name"]
    )

    # ── 3. membership_applications ─────────────────────────────────────────
    op.create_table(
        "membership_applications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("club_id", UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", UUID(as_uuid=True), nullable=False),
        sa.Column("applicant_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("form_data", JSONB(), nullable=True),
        sa.Column("pdf_object_key", sa.String(500), nullable=True),
        sa.Column("pdf_sha256", sa.String(64), nullable=True),
        sa.Column("signature_object_key", sa.String(500), nullable=True),
        sa.Column("signature_sha256", sa.String(64), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_membership_applications_club_id", "membership_applications", ["club_id"]
    )
    op.create_index(
        "ix_membership_applications_person_id", "membership_applications", ["person_id"]
    )
    op.create_index(
        "ix_membership_applications_status",
        "membership_applications",
        ["club_id", "status"],
    )

    # ── GRANT (PostgreSQL only) ────────────────────────────────────────────
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON sports_branches TO myk_app;")
        op.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON membership_applications TO myk_app;"
        )

        # ── Seed: her mevcut kulüp için varsayılan branşlar ────────────────
        # Yeni kurulum için clubs tablosu boş olabilir; bu durumda seed atlanır.
        conn = op.get_bind()
        clubs_result = conn.execute(sa.text("SELECT id FROM clubs"))
        clubs = clubs_result.fetchall()
        for (club_id,) in clubs:
            for i, branch_name in enumerate(SEED_BRANCHES):
                conn.execute(
                    sa.text(
                        "INSERT INTO sports_branches (id, club_id, name, sort_order) "
                        "VALUES (gen_random_uuid(), :club_id, :name, :sort_order) "
                        "ON CONFLICT (club_id, name) DO NOTHING"
                    ),
                    {"club_id": str(club_id), "name": branch_name, "sort_order": i},
                )


def downgrade() -> None:
    op.drop_table("membership_applications")
    op.drop_table("sports_branches")
    op.drop_column("persons", "avatar_object_key")
    op.add_column(
        "persons",
        sa.Column("avatar_url", sa.String(500), nullable=True),
    )
