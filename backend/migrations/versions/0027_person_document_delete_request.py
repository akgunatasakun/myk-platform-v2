"""Kişisel evrak silme isteği — delete_request JSON kolonu.

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-05

person_documents tablosuna nullable Text kolonu eklenir; silme isteği
JSON blob olarak saklanır: {reason, requested_by_user_id, status, created_at}.
"""
import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.add_column(
        "person_documents",
        sa.Column("delete_request", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_column("person_documents", "delete_request")
