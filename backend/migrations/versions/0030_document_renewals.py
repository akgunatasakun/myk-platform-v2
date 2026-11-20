"""Poliçe ve sözleşme yenileme dönemleri."""

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "doc_documents",
        sa.Column(
            "management_only", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.execute(
        "UPDATE doc_documents SET management_only = true WHERE code LIKE 'MYK-POL-%' OR code LIKE 'MYK-SOZ-%'"
    )
    op.create_table(
        "document_renewals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "club_id",
            sa.Uuid(),
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("doc_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "previous_id",
            sa.Uuid(),
            sa.ForeignKey("document_renewals.id", ondelete="SET NULL"),
            nullable=True,
            unique=True,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("reference_no", sa.String(128), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("warning_days", sa.Integer(), nullable=False),
        sa.Column("annual", sa.Boolean(), nullable=False),
        sa.Column(
            "responsible_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_closed", sa.Boolean(), nullable=False),
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
        sa.CheckConstraint("kind IN ('police','sozlesme')", name="ck_renewals_kind"),
        sa.CheckConstraint(
            "warning_days BETWEEN 1 AND 365", name="ck_renewals_warning"
        ),
        sa.CheckConstraint(
            "expires_on IS NULL OR starts_on IS NULL OR expires_on >= starts_on",
            name="ck_renewals_dates",
        ),
    )
    for col in ("club_id", "document_id", "expires_on"):
        op.create_index("ix_document_renewals_" + col, "document_renewals", [col])
    op.create_index(
        "uq_renewals_open_document",
        "document_renewals",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("is_closed = false"),
        sqlite_where=sa.text("is_closed = 0"),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON document_renewals TO myk_app"
        )


def downgrade():
    op.drop_table("document_renewals")
    op.drop_column("doc_documents", "management_only")
