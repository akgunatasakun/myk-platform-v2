"""Academy veri modeli — program/modül/ders hiyerarşisi, kayıt, seans, ilerleme ve quiz.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-09

Değişiklikler (10 tablo):
  1. academy_programs     — ders programı kataloğu (global veya kulübe özel)
  2. academy_modules      — program içindeki modüller
  3. academy_lessons      — modül içindeki dersler (slug global unique)
  4. academy_lesson_steps — ders adımları (video, metin, quiz, vb.)
  5. academy_enrollments  — öğrenci-program kayıtları
  6. academy_sessions     — ders seans kaydı (heartbeat takibi)
  7. academy_progress     — kişi başına ders ilerleme durumu
  8. academy_quiz_questions — quiz soruları (correct_letter sadece backend)
  9. academy_quiz_attempts  — quiz girişimi kayıtları
 10. academy_quiz_answers   — girişim başına cevaplar
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    _u = UUID(as_uuid=True) if is_pg else sa.String(36)
    _json = JSONB() if is_pg else sa.JSON()

    # ── 1. academy_programs ───────────────────────────────────────────────
    op.create_table(
        "academy_programs",
        sa.Column("id", _u, nullable=False),
        sa.Column("club_id", _u, nullable=True),  # NULL = global katalog
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("ad", sa.Text(), nullable=False),
        sa.Column("kod", sa.Text(), nullable=False),
        sa.Column("aciklama", sa.Text(), nullable=True),
        sa.Column("seviye", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("aktif", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.PrimaryKeyConstraint("id", name="pk_academy_programs"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("slug", name="uq_academy_programs_slug"),
    )

    # ── 2. academy_modules ────────────────────────────────────────────────
    op.create_table(
        "academy_modules",
        sa.Column("id", _u, nullable=False),
        sa.Column("program_id", _u, nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("ad", sa.Text(), nullable=False),
        sa.Column("sira", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("aktif", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_academy_modules"),
        sa.ForeignKeyConstraint(
            ["program_id"], ["academy_programs.id"], ondelete="CASCADE"
        ),
    )

    # ── 3. academy_lessons ────────────────────────────────────────────────
    op.create_table(
        "academy_lessons",
        sa.Column("id", _u, nullable=False),
        sa.Column("module_id", _u, nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("ad", sa.Text(), nullable=False),
        sa.Column("aciklama", sa.Text(), nullable=True),
        sa.Column("ders_tipi", sa.Text(), nullable=False, server_default="'knot'"),
        sa.Column("tahmini_sure_dk", sa.Integer(), nullable=True),
        sa.Column("sira", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("aktif", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.PrimaryKeyConstraint("id", name="pk_academy_lessons"),
        sa.ForeignKeyConstraint(
            ["module_id"], ["academy_modules.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("slug", name="uq_academy_lessons_slug"),
    )

    # ── 4. academy_lesson_steps ───────────────────────────────────────────
    op.create_table(
        "academy_lesson_steps",
        sa.Column("id", _u, nullable=False),
        sa.Column("lesson_id", _u, nullable=False),
        sa.Column("sira", sa.Integer(), nullable=False),
        sa.Column("tip", sa.Text(), nullable=False),
        sa.Column("baslik", sa.Text(), nullable=True),
        sa.Column("data_json", _json, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_academy_lesson_steps"),
        sa.ForeignKeyConstraint(
            ["lesson_id"], ["academy_lessons.id"], ondelete="CASCADE"
        ),
    )

    # ── 5. academy_enrollments ────────────────────────────────────────────
    op.create_table(
        "academy_enrollments",
        sa.Column("id", _u, nullable=False),
        sa.Column("club_id", _u, nullable=False),
        sa.Column("person_id", _u, nullable=False),
        sa.Column("program_id", _u, nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="'active'"),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_academy_enrollments"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["program_id"], ["academy_programs.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "club_id",
            "person_id",
            "program_id",
            name="uq_academy_enrollments_club_person_program",
        ),
    )
    op.create_index(
        "ix_academy_enrollments_club_person",
        "academy_enrollments",
        ["club_id", "person_id"],
    )

    # ── 6. academy_sessions ───────────────────────────────────────────────
    op.create_table(
        "academy_sessions",
        sa.Column("id", _u, nullable=False),
        sa.Column("club_id", _u, nullable=False),
        sa.Column("user_id", _u, nullable=False),
        sa.Column("person_id", _u, nullable=False),
        sa.Column("lesson_id", _u, nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_hash", sa.Text(), nullable=True),  # HMAC-SHA256, KVKK
        sa.PrimaryKeyConstraint("id", name="pk_academy_sessions"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["lesson_id"], ["academy_lessons.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_academy_sessions_lesson",
        "academy_sessions",
        ["lesson_id"],
    )

    # ── 7. academy_progress ───────────────────────────────────────────────
    op.create_table(
        "academy_progress",
        sa.Column("id", _u, nullable=False),
        sa.Column("club_id", _u, nullable=False),
        sa.Column("person_id", _u, nullable=False),
        sa.Column("lesson_id", _u, nullable=False),
        sa.Column("tamamlandi", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("yuzde", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("toplam_sure_sn", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("son_adim_sira", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_academy_progress"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["lesson_id"], ["academy_lessons.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "club_id",
            "person_id",
            "lesson_id",
            name="uq_academy_progress_club_person_lesson",
        ),
    )
    op.create_index(
        "ix_academy_progress_club_person",
        "academy_progress",
        ["club_id", "person_id"],
    )

    # ── 8. academy_quiz_questions ─────────────────────────────────────────
    op.create_table(
        "academy_quiz_questions",
        sa.Column("id", _u, nullable=False),
        sa.Column("lesson_id", _u, nullable=False),
        sa.Column("sira", sa.Integer(), nullable=False),
        sa.Column("soru_metni", sa.Text(), nullable=False),
        sa.Column("options", _json, nullable=False),  # [{"harf": "A", "metin": "..."}]
        sa.Column("correct_letter", sa.Text(), nullable=False),  # BACKEND-ONLY
        sa.Column("aciklama", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_academy_quiz_questions"),
        sa.ForeignKeyConstraint(
            ["lesson_id"], ["academy_lessons.id"], ondelete="CASCADE"
        ),
    )

    # ── 9. academy_quiz_attempts ──────────────────────────────────────────
    op.create_table(
        "academy_quiz_attempts",
        sa.Column("id", _u, nullable=False),
        sa.Column("club_id", _u, nullable=False),
        sa.Column("person_id", _u, nullable=False),
        sa.Column("lesson_id", _u, nullable=False),
        sa.Column(
            "basladi_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("bitti_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dogru", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("toplam", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gecti", sa.Boolean(), nullable=True),  # None = henüz bitmedi
        sa.PrimaryKeyConstraint("id", name="pk_academy_quiz_attempts"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["lesson_id"], ["academy_lessons.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_academy_quiz_attempts_person_lesson",
        "academy_quiz_attempts",
        ["person_id", "lesson_id"],
    )

    # ── 10. academy_quiz_answers ──────────────────────────────────────────
    op.create_table(
        "academy_quiz_answers",
        sa.Column("id", _u, nullable=False),
        sa.Column("club_id", _u, nullable=False),
        sa.Column("attempt_id", _u, nullable=False),
        sa.Column("question_id", _u, nullable=False),
        sa.Column("secilen_harf", sa.Text(), nullable=False),
        sa.Column("dogru_mu", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_academy_quiz_answers"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["academy_quiz_attempts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["question_id"], ["academy_quiz_questions.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "attempt_id",
            "question_id",
            name="uq_academy_quiz_answers_attempt_question",
        ),
    )

    # ── PostgreSQL GRANT ──────────────────────────────────────────────────
    if is_pg:
        tables = [
            "academy_programs",
            "academy_modules",
            "academy_lessons",
            "academy_lesson_steps",
            "academy_enrollments",
            "academy_sessions",
            "academy_progress",
            "academy_quiz_questions",
            "academy_quiz_attempts",
            "academy_quiz_answers",
        ]
        for table in tables:
            op.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO myk_app;"
            )


def downgrade() -> None:
    # Bağımlılık sırasına göre — alt tablolar önce
    op.drop_table("academy_quiz_answers")
    op.drop_index("ix_academy_quiz_attempts_person_lesson", "academy_quiz_attempts")
    op.drop_table("academy_quiz_attempts")
    op.drop_table("academy_quiz_questions")
    op.drop_index("ix_academy_progress_club_person", "academy_progress")
    op.drop_table("academy_progress")
    op.drop_index("ix_academy_sessions_lesson", "academy_sessions")
    op.drop_table("academy_sessions")
    op.drop_index("ix_academy_enrollments_club_person", "academy_enrollments")
    op.drop_table("academy_enrollments")
    op.drop_table("academy_lesson_steps")
    op.drop_table("academy_lessons")
    op.drop_table("academy_modules")
    op.drop_table("academy_programs")
