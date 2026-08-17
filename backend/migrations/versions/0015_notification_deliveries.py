"""notification_deliveries — alıcı bazlı gönderim izleme.

Sprint 15B: Kişi bazlı alıcı çözümleme.

Tasarım kararları:
  - Retry, event seviyesinde değil delivery seviyesinde yönetilir.
    Böylece bir veliye gönderim başarısız olsa diğer veliye tekrar mail
    gitmez; yalnızca başarısız delivery yeniden denenir.
  - UNIQUE(event_id, recipient_email, channel): idempotent dispatch;
    aynı alıcıya aynı event için aynı kanaldan iki kez kayıt açılmaz.
  - Event, tüm delivery kayıtları terminal duruma (done/failed) gelince
    'done' olarak işaretlenir.
  - recipient_person_id nullable: kulüp genel e-postası gibi person
    bağlantısı olmayan alıcılar için NULL bırakılır.

Revision ID: 0015
Revises   : 0014
"""

from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("recipient_person_id", sa.UUID(), nullable=True),
        sa.Column("recipient_email", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False, server_default="email"),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["club_id"], ["clubs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["domain_events.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["recipient_person_id"], ["persons.id"], ondelete="SET NULL"
        ),
    )

    # İdempotent dispatch: aynı event+alıcı+kanal için tek kayıt
    op.create_index(
        "uq_notification_deliveries_per_event",
        "notification_deliveries",
        ["event_id", "recipient_email", "channel"],
        unique=True,
    )

    # Dispatch kuyruğu sorgu hızlandırma
    op.create_index(
        "ix_notification_deliveries_dispatch_queue",
        "notification_deliveries",
        ["club_id", "status", "next_attempt_at"],
    )

    # Event bazlı toplu sorgular için
    op.create_index(
        "ix_notification_deliveries_event_id",
        "notification_deliveries",
        ["event_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_deliveries_event_id", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_dispatch_queue", table_name="notification_deliveries")
    op.drop_index("uq_notification_deliveries_per_event", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
