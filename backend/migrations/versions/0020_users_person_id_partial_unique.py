"""users.person_id partial unique index (soft-delete uyumlu)

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-23

Amaç:
  Bir Person kaydı yalnızca tek bir aktif (is_deleted=false) User'a bağlanabilsin.
  Silinmiş (is_deleted=true) hesaplar bu kısıtın dışında tutulur; böylece
  soft-delete → restore döngüsü ve tarihsel audit kaydı bozulmaz.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Partial unique: sadece person_id dolu VE silinmemiş satırlar için kısıt
    op.execute("""
        CREATE UNIQUE INDEX uq_users_person_id_active
        ON users (person_id)
        WHERE person_id IS NOT NULL
          AND is_deleted IS FALSE
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_users_person_id_active")
