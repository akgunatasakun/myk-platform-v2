"""Sporcuyu oluşturan kullanıcı ve antrenör erişim kapsamı."""
import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("persons") as batch:
        batch.add_column(sa.Column("created_by_user_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_persons_created_by_user", "users", ["created_by_user_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_persons_created_by_user_id", ["created_by_user_id"])


def downgrade():
    with op.batch_alter_table("persons") as batch:
        batch.drop_index("ix_persons_created_by_user_id")
        batch.drop_constraint("fk_persons_created_by_user", type_="foreignkey")
        batch.drop_column("created_by_user_id")
