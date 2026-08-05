"""Üyelik yaşam döngüsü için şema değişiklikleri.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-06

Değişiklikler:
  - persons.member_number: kulüp içinde benzersiz üye numarası
  - persons.must_change_password: ilk girişte şifre değiştirme zorunluluğu
  - users.person_id: kullanıcı hesabını kişi kaydına bağlar (nullable)
  - member_counters: yarış koşuluna dayanıklı üye numarası üretimi
  - password_reset_tokens: şifre sıfırlama akışı için
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # ── 1. persons — member_number ve must_change_password ────────────────
    op.add_column(
        "persons",
        sa.Column("member_number", sa.String(20), nullable=True),
    )
    op.add_column(
        "persons",
        sa.Column("must_change_password", sa.Boolean(), nullable=False,
                  server_default="false"),
    )

    # member_number kulüp içinde benzersiz (NULL'lar hariç)
    # PostgreSQL partial index, SQLite normal unique constraint
    if is_pg:
        op.create_index(
            "ix_persons_member_number",
            "persons",
            ["club_id", "member_number"],
            unique=True,
            postgresql_where=sa.text("member_number IS NOT NULL"),
        )
    else:
        # SQLite: unique index, NULL değerler unique kısıtını ihlal etmez
        op.create_index(
            "ix_persons_member_number",
            "persons",
            ["club_id", "member_number"],
        )

    # ── 2. users — person_id ──────────────────────────────────────────────
    op.add_column(
        "users",
        sa.Column("person_id", UUID(as_uuid=True) if is_pg else sa.String(36),
                  nullable=True),
    )
    if is_pg:
        op.create_foreign_key(
            "fk_users_person",
            "users",
            "persons",
            ["person_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_users_person_id", "users", ["person_id"])

    # ── 3. member_counters — yarış koşuluna dayanıklı numara üretimi ──────
    op.create_table(
        "member_counters",
        sa.Column("club_id", UUID(as_uuid=True) if is_pg else sa.String(36),
                  nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("club_id", "year", name="pk_member_counters"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
    )

    # ── 4. password_reset_tokens ──────────────────────────────────────────
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", UUID(as_uuid=True) if is_pg else sa.String(36),
                  nullable=False),
        sa.Column("user_id", UUID(as_uuid=True) if is_pg else sa.String(36),
                  nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_password_reset_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_hash"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_prt_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_prt_token_hash", "password_reset_tokens", ["token_hash"])

    # ── GRANT (PostgreSQL only) ───────────────────────────────────────────
    if is_pg:
        for table in ("member_counters", "password_reset_tokens"):
            op.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO myk_app;"
            )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # password_reset_tokens
    op.drop_index("ix_prt_token_hash", "password_reset_tokens")
    op.drop_index("ix_prt_user_id", "password_reset_tokens")
    op.drop_table("password_reset_tokens")

    # member_counters
    op.drop_table("member_counters")

    # users.person_id
    if is_pg:
        op.drop_constraint("fk_users_person", "users", type_="foreignkey")
    op.drop_index("ix_users_person_id", "users")
    op.drop_column("users", "person_id")

    # persons.must_change_password ve member_number
    op.drop_index("ix_persons_member_number", "persons")
    op.drop_column("persons", "must_change_password")
    op.drop_column("persons", "member_number")
