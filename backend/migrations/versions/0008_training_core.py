"""Training Core — fiziksel yelken eğitimi: kurs, oturum, kayıt, yoklama.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-10

Değişiklikler (4 tablo):
  1. training_courses     — fiziksel kurs tanımları (sinif, seviye, egitmen)
  2. training_sessions    — ders oturumları (tarih, saat; normalize edilmiş katman)
  3. training_enrollments — kişi-kurs kayıtları (kapasite kontrollü, soft-cancel)
  4. training_attendance  — oturum bazlı yoklama (var/yok/izinli/gecikti)

Domain notu: Bu tablolar Academy (0007) ile tamamen ayrıdır. Aralarında FK yok.
Kimlik prensibi: katılımcı/eğitmen = persons.id; işlemi yapan = users.id.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    _u = UUID(as_uuid=True) if is_pg else sa.String(36)

    # ── 1. training_courses ───────────────────────────────────────────────────
    op.create_table(
        "training_courses",
        sa.Column("id", _u, nullable=False),
        sa.Column("club_id", _u, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("class_name", sa.Text(), nullable=True),        # eski: sinif
        sa.Column("level", sa.Text(), nullable=True),             # eski: seviye
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("schedule_text", sa.Text(), nullable=True),     # eski: gun_saatleri
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fee", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("instructor_person_id", _u, nullable=True),     # eski: egitmen_id → persons
        sa.Column("status", sa.Text(), nullable=False, server_default="'planlandi'"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
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
        sa.PrimaryKeyConstraint("id", name="pk_training_courses"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["instructor_person_id"], ["persons.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_training_courses_club_status",
        "training_courses",
        ["club_id", "status"],
    )
    op.create_index(
        "ix_training_courses_instructor",
        "training_courses",
        ["club_id", "instructor_person_id"],
    )

    # ── 2. training_sessions ──────────────────────────────────────────────────
    op.create_table(
        "training_sessions",
        sa.Column("id", _u, nullable=False),
        sa.Column("club_id", _u, nullable=False),
        sa.Column("course_id", _u, nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("instructor_person_id", _u, nullable=True),     # oturuma özel eğitmen
        sa.Column("status", sa.Text(), nullable=False, server_default="'planli'"),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_training_sessions"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["course_id"], ["training_courses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["instructor_person_id"], ["persons.id"], ondelete="SET NULL"
        ),
    )
    # NOT: (course_id, session_date) üzerinde DB-level UNIQUE yok.
    # Aynı gün birden fazla oturum (sabah+öğleden sonra) mümkün olmalı.
    # Duplicate kontrolü service katmanında yapılır.
    op.create_index(
        "ix_training_sessions_course_date",
        "training_sessions",
        ["club_id", "course_id", "session_date"],
    )

    # ── 3. training_enrollments ───────────────────────────────────────────────
    op.create_table(
        "training_enrollments",
        sa.Column("id", _u, nullable=False),
        sa.Column("club_id", _u, nullable=False),
        sa.Column("course_id", _u, nullable=False),
        sa.Column("person_id", _u, nullable=False),               # eski: sporcu_id
        sa.Column("status", sa.Text(), nullable=False, server_default="'active'"),
        sa.Column("payment_status", sa.Text(), nullable=False, server_default="'pending'"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
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
        sa.PrimaryKeyConstraint("id", name="pk_training_enrollments"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["course_id"], ["training_courses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_training_enrollments_club_person",
        "training_enrollments",
        ["club_id", "person_id"],
    )
    op.create_index(
        "ix_training_enrollments_club_course",
        "training_enrollments",
        ["club_id", "course_id"],
    )
    # PostgreSQL partial unique: aynı anda yalnızca bir aktif enrollment
    # Eski SQLite UNIQUE(sporcu_id, kurs_id, silinmis_mi) yerine daha temiz yaklaşım
    if is_pg:
        op.execute(
            """
            CREATE UNIQUE INDEX uq_training_enrollments_active
            ON training_enrollments (club_id, course_id, person_id)
            WHERE is_deleted = false AND status = 'active'
            """
        )

    # ── 4. training_attendance ────────────────────────────────────────────────
    op.create_table(
        "training_attendance",
        sa.Column("id", _u, nullable=False),
        sa.Column("club_id", _u, nullable=False),
        sa.Column("session_id", _u, nullable=False),
        sa.Column("person_id", _u, nullable=False),               # eski: sporcu_id
        sa.Column("status", sa.Text(), nullable=False, server_default="'var'"),
        # Kaynak: Flask GECERLI = {'var','yok','izinli','gecikti'}
        sa.Column("check_in_time", sa.Time(), nullable=True),     # eski: giris_saati
        sa.Column("check_out_time", sa.Time(), nullable=True),    # eski: cikis_saati
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by_user_id", _u, nullable=True),      # eski: olusturan_id → users
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
        sa.PrimaryKeyConstraint("id", name="pk_training_attendance"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["training_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "session_id", "person_id",
            name="uq_training_attendance_session_person",
        ),
    )
    op.create_index(
        "ix_training_attendance_session",
        "training_attendance",
        ["club_id", "session_id"],
    )
    op.create_index(
        "ix_training_attendance_person",
        "training_attendance",
        ["club_id", "person_id"],
    )

    # ── PostgreSQL GRANT ──────────────────────────────────────────────────────
    if is_pg:
        tables = [
            "training_courses",
            "training_sessions",
            "training_enrollments",
            "training_attendance",
        ]
        for table in tables:
            op.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO myk_app;"
            )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    op.drop_index("ix_training_attendance_person", "training_attendance")
    op.drop_index("ix_training_attendance_session", "training_attendance")
    op.drop_table("training_attendance")

    if is_pg:
        op.execute("DROP INDEX IF EXISTS uq_training_enrollments_active")
    op.drop_index("ix_training_enrollments_club_course", "training_enrollments")
    op.drop_index("ix_training_enrollments_club_person", "training_enrollments")
    op.drop_table("training_enrollments")

    op.drop_index("ix_training_sessions_course_date", "training_sessions")
    op.drop_table("training_sessions")

    op.drop_index("ix_training_courses_instructor", "training_courses")
    op.drop_index("ix_training_courses_club_status", "training_courses")
    op.drop_table("training_courses")
