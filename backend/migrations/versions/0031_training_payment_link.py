"""Tahsilatları belirli eğitim kayıtlarına bağla; geçmiş kayıtları otomatik eşleştirme."""

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "payments", sa.Column("training_enrollment_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_payments_training_enrollment",
        "payments",
        "training_enrollments",
        ["training_enrollment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_payments_training_enrollment_id", "payments", ["training_enrollment_id"]
    )


def downgrade():
    op.drop_index("ix_payments_training_enrollment_id", table_name="payments")
    op.drop_constraint(
        "fk_payments_training_enrollment", "payments", type_="foreignkey"
    )
    op.drop_column("payments", "training_enrollment_id")
