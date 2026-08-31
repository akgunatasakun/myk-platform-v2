"""membership application preferred training course

Revision ID: 0022
Revises: 0021
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "membership_applications",
        sa.Column("preferred_course_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_membership_applications_preferred_course_id",
        "membership_applications",
        "training_courses",
        ["preferred_course_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_membership_applications_club_preferred_course",
        "membership_applications",
        ["club_id", "preferred_course_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_membership_applications_club_preferred_course",
        table_name="membership_applications",
    )
    op.drop_constraint(
        "fk_membership_applications_preferred_course_id",
        "membership_applications",
        type_="foreignkey",
    )
    op.drop_column("membership_applications", "preferred_course_id")
