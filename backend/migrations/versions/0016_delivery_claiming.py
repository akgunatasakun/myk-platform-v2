"""notification_deliveries — concurrent worker claiming.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-17

Eşzamanlı worker güvenliği için iki alan:
  - processing_since: delivery gönderim denemesine başlandığında set edilir
  - claimed_worker_id: bu alanı dolduran worker'a ait; NULL = serbest

dispatch_pending_deliveries fonksiyonu:
  1. UPDATE SET processing_since=now, claimed_worker_id=<uuid>
       WHERE claimed_worker_id IS NULL AND status='pending'
  2. COMMIT (claim garantilendi)
  3. SELECT WHERE claimed_worker_id=<uuid>
  4. Gönder; başarıda claimed_worker_id=NULL, başarısızlıkta retry

Crash recovery:
  Dispatch başlangıcında, claimed_worker_id IS NOT NULL AND
  processing_since < now - 10dk olan delivery'ler tekrar serbest bırakılır.
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_deliveries",
        sa.Column("processing_since", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("claimed_worker_id", sa.Text(), nullable=True),
    )
    # Recovery index: stuck claim tespiti için
    op.create_index(
        "ix_notification_deliveries_stuck_claims",
        "notification_deliveries",
        ["claimed_worker_id", "processing_since"],
        postgresql_where=sa.text("claimed_worker_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_deliveries_stuck_claims",
        table_name="notification_deliveries",
    )
    op.drop_column("notification_deliveries", "claimed_worker_id")
    op.drop_column("notification_deliveries", "processing_since")
