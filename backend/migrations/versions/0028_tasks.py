"""Kulüp görev yönetimi.

Revision ID: 0028
Revises: 0027
"""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "club_id",
            sa.Uuid(),
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "assigned_person_id",
            sa.Uuid(),
            sa.ForeignKey("persons.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
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
        sa.CheckConstraint(
            "status IN ('acik','devam_ediyor','tamamlandi','iptal')",
            name="ck_tasks_status",
        ),
        sa.CheckConstraint(
            "priority IN ('dusuk','normal','yuksek','acil')", name="ck_tasks_priority"
        ),
    )
    for column in ("club_id", "assigned_person_id", "due_date", "status"):
        op.create_index(f"ix_tasks_{column}", "tasks", [column])

    if op.get_bind().dialect.name == "postgresql":
        op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tasks TO myk_app")


def downgrade() -> None:
    op.drop_table("tasks")
