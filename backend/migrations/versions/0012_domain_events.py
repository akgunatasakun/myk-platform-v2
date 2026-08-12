"""Domain events — event-driven bildirim altyapısı.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-12

Değişiklikler (1 tablo):
  domain_events — platform geneli event/bildirim tablosu.

Tasarım notları:
  - status: 'pending' | 'processing' | 'done' | 'failed'
  - scheduled_for: datetime(tz) — nightly scan olaylarında üretim tarihi,
    anlık olaylarda oluşturma zamanı. future event scheduling için de kullanılabilir.
  - acknowledged_at: kulüp-seviyesinde "okundu" işareti (MVP: tek yönetim feed'i).
    Gelecekte per-user okuma gerekirse ayrı bir tablo eklenir.
  - Partial unique index: (club_id, event_type, aggregate_id, scheduled_for_date)
    → aynı aggregate için aynı gün aynı event tipi yalnızca bir kez üretilir.
    SQLite'ta partial index olmadığından test ortamında atlanır.

Event type naming: '<aggregate>.<action>'
  Örnekler: 'payment.overdue', 'athlete.license.expiring_soon',
            'training.session.starts_tomorrow', 'application.submitted'
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    _U = UUID(as_uuid=True) if is_pg else sa.String(36)

    op.create_table(
        "domain_events",
        sa.Column("id", _U, primary_key=True, nullable=False),
        sa.Column(
            "club_id", _U,
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),          # e.g. 'payment.overdue'
        sa.Column("aggregate_type", sa.Text(), nullable=False),      # e.g. 'payment'
        sa.Column("aggregate_id", sa.Text(), nullable=True),         # str(uuid) or slug
        sa.Column("payload", sa.JSON(), nullable=True),              # event-specific data
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        # scheduled_for: UTC datetime — nightly jobs için tarama günü başlangıcı
        sa.Column(
            "scheduled_for",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Partial unique index: aynı gün duplicate event engeli.
    # Yalnızca PostgreSQL'de oluşturulur (SQLite test ortamı bunu desteklemez).
    if is_pg:
        op.create_index(
            "uq_domain_events_daily",
            "domain_events",
            ["club_id", "event_type", "aggregate_id",
             sa.text("date(scheduled_for AT TIME ZONE 'UTC')")],
            unique=True,
            postgresql_where=sa.text("aggregate_id IS NOT NULL AND scheduled_for IS NOT NULL"),
        )

    # Genel sorgular için composite index
    op.create_index(
        "ix_domain_events_club_status_created",
        "domain_events",
        ["club_id", "status", "created_at"],
    )
    op.create_index(
        "ix_domain_events_club_ack",
        "domain_events",
        ["club_id", "acknowledged_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        op.drop_index("uq_domain_events_daily", table_name="domain_events")

    op.drop_index("ix_domain_events_club_ack", table_name="domain_events")
    op.drop_index("ix_domain_events_club_status_created", table_name="domain_events")
    op.drop_table("domain_events")
