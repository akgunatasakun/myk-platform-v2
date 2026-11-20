"""Kulüp eğitim sertifikası kayıtları."""

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "training_certificates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "club_id",
            sa.Uuid(),
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "enrollment_id",
            sa.Uuid(),
            sa.ForeignKey("training_enrollments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("person_name", sa.String(300), nullable=False),
        sa.Column("course_name", sa.String(240), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("number", sa.String(64), nullable=True),
        sa.Column("issued_on", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "issued_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "revoked_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
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
        sa.UniqueConstraint("club_id", "number", name="uq_certificates_club_number"),
        sa.CheckConstraint(
            "status IN ('draft', 'issued', 'revoked')", name="ck_certificates_status"
        ),
        sa.CheckConstraint(
            "status = 'draft' OR (number IS NOT NULL AND issued_on IS NOT NULL)",
            name="ck_certificates_issued_fields",
        ),
        sa.CheckConstraint(
            "expires_on IS NULL OR issued_on IS NULL OR expires_on >= issued_on",
            name="ck_certificates_dates",
        ),
    )
    for field in ["club_id", "enrollment_id"]:
        op.create_index(
            "ix_training_certificates_" + field, "training_certificates", [field]
        )
    op.create_index(
        "uq_certificates_live_enrollment",
        "training_certificates",
        ["club_id", "enrollment_id"],
        unique=True,
        postgresql_where=sa.text(
            "is_deleted = false AND status IN ('draft', 'issued')"
        ),
        sqlite_where=sa.text("is_deleted = 0 AND status IN ('draft', 'issued')"),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON training_certificates TO myk_app"
        )


def downgrade():
    op.drop_table("training_certificates")
