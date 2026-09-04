"""Veli yetkileri ve kişisel evrak çekirdek tabloları.

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-04

Bu migration yalnız PostgreSQL'de çalışır. SQLite birim testlerinde mevcut
create_all akışı kullanılmaya devam eder.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


DOCUMENT_TYPES = (
    "profile_photo",
    "identity_copy",
    "health_report",
    "parental_permission",
    "undertaking",
    "waiver",
    "other",
)
REVIEW_STATUSES = ("pending", "approved", "rejected", "expired", "superseded")
SCAN_STATUSES = ("pending", "clean", "infected", "failed", "skipped_dev")


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.add_column(
        "person_guardians",
        sa.Column("can_consent", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "person_guardians",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "person_guardians",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "person_guardians",
        sa.Column("revoked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_person_guardians_revoked_by_user_id_users",
        "person_guardians",
        "users",
        ["revoked_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        sa.text("UPDATE person_guardians SET can_consent = true WHERE is_primary IS TRUE")
    )

    op.create_table(
        "person_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "club_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subject_person_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("persons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "guardian_link_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("person_guardians.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False, unique=True),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("retain_until", sa.Date(), nullable=True),
        sa.Column(
            "review_status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "scan_status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "supersedes_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("person_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "reviewed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_basis", sa.String(128), nullable=True),
        sa.CheckConstraint(
            f"document_type IN ({_sql_values(DOCUMENT_TYPES)})",
            name="ck_person_documents_document_type",
        ),
        sa.CheckConstraint(
            f"review_status IN ({_sql_values(REVIEW_STATUSES)})",
            name="ck_person_documents_review_status",
        ),
        sa.CheckConstraint(
            f"scan_status IN ({_sql_values(SCAN_STATUSES)})",
            name="ck_person_documents_scan_status",
        ),
        sa.CheckConstraint(
            "document_type <> 'health_report' OR is_sensitive IS TRUE",
            name="ck_person_documents_health_sensitive",
        ),
    )
    op.create_index(
        "ix_person_documents_club_subject_deleted",
        "person_documents",
        ["club_id", "subject_person_id", "is_deleted"],
    )
    op.create_index(
        "ix_person_documents_club_type_scan",
        "person_documents",
        ["club_id", "document_type", "scan_status"],
    )

    op.create_table(
        "person_document_representatives",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("person_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("persons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "guardian_link_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("person_guardians.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("representative_role", sa.String(64), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "document_id",
            "person_id",
            "representative_role",
            name="uq_person_document_representative_role",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_table("person_document_representatives")
    op.drop_index(
        "ix_person_documents_club_type_scan", table_name="person_documents"
    )
    op.drop_index(
        "ix_person_documents_club_subject_deleted", table_name="person_documents"
    )
    op.drop_table("person_documents")

    op.drop_constraint(
        "fk_person_guardians_revoked_by_user_id_users",
        "person_guardians",
        type_="foreignkey",
    )
    op.drop_column("person_guardians", "revoked_by_user_id")
    op.drop_column("person_guardians", "revoked_at")
    op.drop_column("person_guardians", "is_active")
    op.drop_column("person_guardians", "can_consent")
