"""domain_events retry alanları — attempt_count, last_error, next_attempt_at.

Sprint 15A: Dispatch sağlamlaştırma.
  - attempt_count  : kaç kez denendi (0 = henüz denenmedi)
  - last_error     : en son SMTP/dispatch hata mesajı
  - next_attempt_at: bir sonraki deneme zamanı (NULL = hemen uygun)

Backoff takvimi (dispatch_pending_events içinde hesaplanır):
  deneme 1 başarısız → next_attempt_at = now + 5  dk
  deneme 2 başarısız → next_attempt_at = now + 25 dk  (5 * 5)
  deneme 3 başarısız → status = 'failed', next_attempt_at NULL

Revision ID: 0014
Revises   : 0013
"""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "domain_events",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "domain_events",
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "domain_events",
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    # Dispatch sorgusunu hızlandırmak için index
    op.create_index(
        "ix_domain_events_dispatch_queue",
        "domain_events",
        ["club_id", "status", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_domain_events_dispatch_queue", table_name="domain_events")
    op.drop_column("domain_events", "next_attempt_at")
    op.drop_column("domain_events", "last_error")
    op.drop_column("domain_events", "attempt_count")
