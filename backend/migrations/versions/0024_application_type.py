"""0024 — membership_applications.application_type alanı.

Kapsam:
  - application_type VARCHAR(20) NOT NULL DEFAULT 'membership'
  - CHECK (membership|course)
  - Backfill: preferred_course_id IS NOT NULL OR program_preference IS NOT NULL → 'course'

Revision: 0024
Down:      0023
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Kolonu server_default ile ekle (var olan satırlar 'membership' alır)
    op.add_column(
        "membership_applications",
        sa.Column(
            "application_type",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'membership'"),
        ),
    )

    # 2. CHECK constraint
    op.create_check_constraint(
        "ck_membership_applications_application_type",
        "membership_applications",
        "application_type IN ('membership', 'course')",
    )

    # 3. Backfill: kurs bilgisi olan kayıtlar → 'course'
    op.execute(
        sa.text(
            """
            UPDATE membership_applications
               SET application_type = 'course'
             WHERE preferred_course_id IS NOT NULL
                OR program_preference IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_membership_applications_application_type",
        "membership_applications",
        type_="check",
    )
    op.drop_column("membership_applications", "application_type")
