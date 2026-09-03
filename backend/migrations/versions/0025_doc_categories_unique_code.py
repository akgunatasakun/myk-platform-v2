"""doc_categories — club_id/code tam unique kısıt.

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-03

0013 migrasyonunda oluşturulan kısmi (is_active = true) unique index,
uygulama düzeyinde 409 kontrolünü desteklemez (pasif kategorilerde boşluk).
Bu migrasyon tam UNIQUE(club_id, code) kısıtıyla değiştirir.

Tasarım notu:
  - SQLite test ortamı partial index desteklemediğinden sadece PostgreSQL'de çalışır.
  - downgrade: tam index'i kaldırır, kısmi index'i geri yükler.
"""
import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite test ortamı — migration atlanır

    # 0013'teki kısmi unique index'i kaldır
    op.drop_index("uq_doc_categories_code", table_name="doc_categories")

    # Tam UNIQUE(club_id, code) kısıtı ekle
    op.create_index(
        "uq_doc_categories_club_code",
        "doc_categories",
        ["club_id", "code"],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_index("uq_doc_categories_club_code", table_name="doc_categories")

    # Kısmi unique index'i geri yükle
    op.create_index(
        "uq_doc_categories_code",
        "doc_categories",
        ["club_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
