"""DMS Core — Belge Yönetim Sistemi temel tabloları.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-13

Değişiklikler (4 tablo):
  doc_categories      — belge kategorileri
  doc_documents       — belgeler (metadata, soft-delete)
  doc_revisions       — her belgenin revizyonları
  doc_revision_files  — revizyon başına dosya depolama

Tasarım notları:
  - doc_documents.current_revision_id circular ref — FK constraint yok, servis yönetir.
  - Partial unique index'ler yalnızca PostgreSQL'de oluşturulur (SQLite test ortamı desteklemez).
  - Boolean kolonlar PostgreSQL native BOOLEAN kullanır.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    _U = UUID(as_uuid=True) if is_pg else sa.String(36)

    # ── doc_categories ────────────────────────────────────────────────────────
    op.create_table(
        "doc_categories",
        sa.Column(
            "id", _U,
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()") if is_pg else None,
        ),
        sa.Column(
            "club_id", _U,
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_doc_categories_club", "doc_categories", ["club_id"])
    if is_pg:
        op.create_index(
            "uq_doc_categories_code",
            "doc_categories",
            ["club_id", "code"],
            unique=True,
            postgresql_where=sa.text("is_active = true"),
        )

    # ── doc_documents ─────────────────────────────────────────────────────────
    doc_doc_constraints = []
    if is_pg:
        doc_doc_constraints.append(
            sa.CheckConstraint(
                "document_type IN ('prosedur','talimati','form','el_kitabi','egitim_materyali',"
                "'operasyonel','sporcu_belgesi','ekipman_belgesi','diger')",
                name="ck_doc_documents_document_type",
            )
        )
        doc_doc_constraints.append(
            sa.CheckConstraint(
                "content_status IN ('tamamlandi','taslak','eksik','placeholder','bilinmiyor')",
                name="ck_doc_documents_content_status",
            )
        )
        doc_doc_constraints.append(
            sa.CheckConstraint(
                "owner_type IS NULL OR owner_type IN ('athlete_profile','person','equipment','club',"
                "'training_course','training_session','diger')",
                name="ck_doc_documents_owner_type",
            )
        )

    op.create_table(
        "doc_documents",
        sa.Column(
            "id", _U,
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()") if is_pg else None,
        ),
        sa.Column(
            "club_id", _U,
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id", _U,
            sa.ForeignKey("doc_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("code", sa.String(128), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("content_status", sa.String(32), nullable=False, server_default="taslak"),
        sa.Column("owner_type", sa.String(64), nullable=True),
        sa.Column("owner_id", _U, nullable=True),
        # current_revision_id: NO FK constraint (circular ref — service manages)
        sa.Column("current_revision_id", _U, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_by_user_id", _U,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        *doc_doc_constraints,
    )
    op.create_index("ix_doc_documents_club", "doc_documents", ["club_id"])
    op.create_index("ix_doc_documents_type", "doc_documents", ["club_id", "document_type"])
    op.create_index("ix_doc_documents_status", "doc_documents", ["club_id", "content_status"])
    op.create_index(
        "ix_doc_documents_owner", "doc_documents",
        ["club_id", "owner_type", "owner_id"],
    )
    if is_pg:
        op.create_index(
            "uq_doc_documents_code",
            "doc_documents",
            ["club_id", "code"],
            unique=True,
            postgresql_where=sa.text("is_deleted = false"),
        )

    # ── doc_revisions ─────────────────────────────────────────────────────────
    rev_constraints = []
    if is_pg:
        rev_constraints.append(
            sa.CheckConstraint(
                "status IN ('taslak','incelemede','onaylandi','yayinda','arsivlendi','bloke')",
                name="ck_doc_revisions_status",
            )
        )

    op.create_table(
        "doc_revisions",
        sa.Column(
            "id", _U,
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()") if is_pg else None,
        ),
        sa.Column(
            "document_id", _U,
            sa.ForeignKey("doc_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision_code", sa.String(32), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=True),
        sa.Column("revision_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="taslak"),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(255), nullable=True),
        sa.Column("manifest_row_id", sa.String(255), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_by_user_id", _U,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        *rev_constraints,
    )
    op.create_index("ix_doc_revisions_document", "doc_revisions", ["document_id"])
    op.create_index(
        "uq_doc_revisions_code",
        "doc_revisions",
        ["document_id", "revision_code"],
        unique=True,
    )
    if is_pg:
        op.create_index(
            "uq_doc_revisions_current",
            "doc_revisions",
            ["document_id"],
            unique=True,
            postgresql_where=sa.text("is_current = true"),
        )

    # ── doc_revision_files ────────────────────────────────────────────────────
    file_constraints = []
    if is_pg:
        file_constraints.append(
            sa.CheckConstraint(
                "file_role IN ('source','published','attachment','signed','rendered','other')",
                name="ck_doc_revision_files_file_role",
            )
        )

    op.create_table(
        "doc_revision_files",
        sa.Column(
            "id", _U,
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()") if is_pg else None,
        ),
        sa.Column(
            "revision_id", _U,
            sa.ForeignKey("doc_revisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_role", sa.String(32), nullable=False, server_default="source"),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_bucket", sa.String(128), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        *file_constraints,
    )
    op.create_index("ix_doc_revision_files_revision", "doc_revision_files", ["revision_id"])
    op.create_index("ix_doc_revision_files_sha256", "doc_revision_files", ["sha256"])
    op.create_index(
        "uq_doc_revision_files_sha256",
        "doc_revision_files",
        ["revision_id", "sha256"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_doc_revision_files_sha256", table_name="doc_revision_files")
    op.drop_index("ix_doc_revision_files_sha256", table_name="doc_revision_files")
    op.drop_index("ix_doc_revision_files_revision", table_name="doc_revision_files")
    op.drop_table("doc_revision_files")

    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        op.drop_index("uq_doc_revisions_current", table_name="doc_revisions")
    op.drop_index("uq_doc_revisions_code", table_name="doc_revisions")
    op.drop_index("ix_doc_revisions_document", table_name="doc_revisions")
    op.drop_table("doc_revisions")

    if is_pg:
        op.drop_index("uq_doc_documents_code", table_name="doc_documents")
    op.drop_index("ix_doc_documents_owner", table_name="doc_documents")
    op.drop_index("ix_doc_documents_status", table_name="doc_documents")
    op.drop_index("ix_doc_documents_type", table_name="doc_documents")
    op.drop_index("ix_doc_documents_club", table_name="doc_documents")
    op.drop_table("doc_documents")

    if is_pg:
        op.drop_index("uq_doc_categories_code", table_name="doc_categories")
    op.drop_index("ix_doc_categories_club", table_name="doc_categories")
    op.drop_table("doc_categories")
