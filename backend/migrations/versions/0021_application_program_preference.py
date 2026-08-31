"""membership_applications.program_preference — eğitim programı tercihi

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-31

Amaç:
  Üyelik başvurularına başvuranın ilk program tercihini kaydetmek için
  program_preference VARCHAR(50) NULL kolonu ve CHECK kısıtı eklenir.

İzin verilen değerler: optimist, ilca, 420, wing_foil, para_yelken
(NULL = tercih belirtilmemiş — eski başvurularla geriye dönük uyumlu)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ALLOWED = ("optimist", "ilca", "420", "wing_foil", "para_yelken")
_CHECK_NAME = "ck_membership_applications_program_preference"
_CHECK_EXPR = (
    "program_preference IS NULL OR program_preference IN "
    "('optimist', 'ilca', '420', 'wing_foil', 'para_yelken')"
)


def upgrade() -> None:
    op.add_column(
        "membership_applications",
        sa.Column("program_preference", sa.String(50), nullable=True),
    )
    op.create_check_constraint(
        _CHECK_NAME,
        "membership_applications",
        _CHECK_EXPR,
    )


def downgrade() -> None:
    op.drop_constraint(_CHECK_NAME, "membership_applications", type_="check")
    op.drop_column("membership_applications", "program_preference")
