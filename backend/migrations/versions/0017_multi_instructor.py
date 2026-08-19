"""training_course_instructors ve training_session_instructors tabloları.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-19

Çoklu antrenör desteği (P0-2):
  - training_course_instructors: kurs ↔ antrenör N:M junction
  - training_session_instructors: oturum ↔ antrenör N:M junction

Aşamalı geçiş:
  - Mevcut instructor_person_id verileri junction tablolara kopyalanır.
  - Eski sütunlar bu sprint'te SİLİNMEZ (bir sonraki sprint'te).
  - Yeni API hem eski sütunları hem junction tabloları günceller.
"""
import uuid as uuid_mod
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── training_course_instructors ────────────────────────────────────────────
    op.create_table(
        "training_course_instructors",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("person_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["training_courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_id", "person_id", name="uq_tci_course_person"),
    )
    op.create_index("ix_tci_course_id", "training_course_instructors", ["course_id"])
    op.create_index("ix_tci_club_id", "training_course_instructors", ["club_id"])

    # ── training_session_instructors ───────────────────────────────────────────
    op.create_table(
        "training_session_instructors",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("person_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["training_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "person_id", name="uq_tsi_session_person"),
    )
    op.create_index("ix_tsi_session_id", "training_session_instructors", ["session_id"])
    op.create_index("ix_tsi_club_id", "training_session_instructors", ["club_id"])

    # ── Veri migrasyonu: mevcut instructor_person_id → junction tabloları ─────
    conn = op.get_bind()

    # Kurs antrenörleri
    course_rows = conn.execute(
        text(
            "SELECT id, club_id, instructor_person_id "
            "FROM training_courses "
            "WHERE instructor_person_id IS NOT NULL"
        )
    ).fetchall()

    for row in course_rows:
        conn.execute(
            text(
                "INSERT INTO training_course_instructors "
                "(id, club_id, course_id, person_id) "
                "VALUES (:id, :club_id, :course_id, :person_id)"
            ),
            {
                "id": uuid_mod.uuid4(),
                "club_id": row[1],
                "course_id": row[0],
                "person_id": row[2],
            },
        )

    # Oturum antrenörleri
    session_rows = conn.execute(
        text(
            "SELECT id, club_id, instructor_person_id "
            "FROM training_sessions "
            "WHERE instructor_person_id IS NOT NULL"
        )
    ).fetchall()

    for row in session_rows:
        conn.execute(
            text(
                "INSERT INTO training_session_instructors "
                "(id, club_id, session_id, person_id) "
                "VALUES (:id, :club_id, :session_id, :person_id)"
            ),
            {
                "id": uuid_mod.uuid4(),
                "club_id": row[1],
                "session_id": row[0],
                "person_id": row[2],
            },
        )


def downgrade() -> None:
    op.drop_index("ix_tsi_club_id", table_name="training_session_instructors")
    op.drop_index("ix_tsi_session_id", table_name="training_session_instructors")
    op.drop_table("training_session_instructors")

    op.drop_index("ix_tci_club_id", table_name="training_course_instructors")
    op.drop_index("ix_tci_course_id", table_name="training_course_instructors")
    op.drop_table("training_course_instructors")
