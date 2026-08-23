"""users.must_change_password alanı — Person'dan User'a taşıma (aşama 1).

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-23

Sprint 18 kullanıcı hesabı yönetimi için must_change_password'ın
tek kaynağını User modeline taşır.

Değişiklikler:
  - users.must_change_password BOOLEAN NOT NULL DEFAULT FALSE eklenir.
  - Backfill: person_id bağlı ve persons.must_change_password=TRUE olan
    User kayıtları User.must_change_password=TRUE yapılır.
  - persons.must_change_password KALIR (uyumluluk); 0021'de kaldırılır.
  - person_id partial unique index BU MIGRATION'DA YOK.
    (Önkoşul: d334a8e1 soft-delete + duplicate audit → 0020)

Downgrade:
  - must_change_password kolonu users tablosundan kaldırılır.
  - Person.must_change_password dokunulmaz (zaten korunuyor).
"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Kolon ekle
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 2. Backfill: bağlı Person'da must_change_password=TRUE olanları User'a yaz.
    #    Yalnızca aktif (is_deleted=FALSE) User'lar güncellenir.
    op.execute(
        sa.text("""
            UPDATE users u
            SET must_change_password = TRUE
            FROM persons p
            WHERE u.person_id = p.id
              AND p.must_change_password IS TRUE
              AND u.is_deleted IS FALSE
        """)
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
