"""PersonGuardian tablosu — veli-sporcu ilişkisi.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-08

Değişiklikler:
  - person_guardians: veli-sporcu bağlantı tablosu
    * unique (club_id, athlete_person_id, guardian_person_id)
    * CHECK athlete_person_id <> guardian_person_id
    * is_primary teklik mantığı application katmanında yönetilir
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    _u = UUID(as_uuid=True) if is_pg else sa.String(36)

    op.create_table(
        "person_guardians",
        sa.Column("id", _u, nullable=False),
        sa.Column("club_id", _u, nullable=False),
        sa.Column("athlete_person_id", _u, nullable=False),
        sa.Column("guardian_person_id", _u, nullable=False),
        sa.Column("relationship_type", sa.String(30), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("can_pickup", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "can_receive_notifications", sa.Boolean(), nullable=False, server_default="true"
        ),
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
        sa.PrimaryKeyConstraint("id", name="pk_person_guardians"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["athlete_person_id"], ["persons.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["guardian_person_id"], ["persons.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "club_id",
            "athlete_person_id",
            "guardian_person_id",
            name="uq_person_guardians_club_athlete_guardian",
        ),
        sa.CheckConstraint(
            "athlete_person_id <> guardian_person_id",
            name="ck_person_guardians_no_self_ref",
        ),
    )

    # (club_id, athlete_person_id) — sporcu veli listesi sorgusu için
    op.create_index(
        "ix_person_guardians_club_athlete",
        "person_guardians",
        ["club_id", "athlete_person_id"],
    )
    # (club_id, guardian_person_id) — veliyi hangi sporcularla ilişkilendirildiğini sorgulamak için
    op.create_index(
        "ix_person_guardians_club_guardian",
        "person_guardians",
        ["club_id", "guardian_person_id"],
    )

    if is_pg:
        op.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON person_guardians TO myk_app;"
        )


def downgrade() -> None:
    op.drop_index("ix_person_guardians_club_guardian", "person_guardians")
    op.drop_index("ix_person_guardians_club_athlete", "person_guardians")
    op.drop_table("person_guardians")
