"""training_courses.attendance_mode alanı.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-19

Yoklama akışını iki moda ayırır:
  - coach_daily      : Antrenör günlük toplu yoklama (Optimist / ILCA vb.)
  - adult_self_checkin: Sporcu kendi hesabıyla check-in yapar (+18 doğrulaması)

Varsayılan coach_daily; mevcut tüm kurslar etkilenmez.
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

# Geçerli mod değerleri
VALID_MODES = ("coach_daily", "adult_self_checkin")


def upgrade() -> None:
    # 1. Enum tipi oluştur (PostgreSQL)
    attendance_mode_enum = sa.Enum(
        *VALID_MODES,
        name="attendancemodeenum",
        create_constraint=True,
        schema=None,
    )
    attendance_mode_enum.create(op.get_bind(), checkfirst=True)

    # 2. Kolonu ekle
    op.add_column(
        "training_courses",
        sa.Column(
            "attendance_mode",
            sa.Enum(*VALID_MODES, name="attendancemodeenum", create_constraint=False),
            nullable=False,
            server_default="coach_daily",
        ),
    )

    # 3. İndeks — mode'a göre filtreleme için
    op.create_index(
        "ix_training_courses_attendance_mode",
        "training_courses",
        ["attendance_mode"],
    )


def downgrade() -> None:
    op.drop_index("ix_training_courses_attendance_mode", table_name="training_courses")
    op.drop_column("training_courses", "attendance_mode")

    # Enum tipini düşür (PostgreSQL)
    sa.Enum(name="attendancemodeenum").drop(op.get_bind(), checkfirst=True)
