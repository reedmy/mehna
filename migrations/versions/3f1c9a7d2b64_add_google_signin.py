"""add google sign-in fields to users

Revision ID: 3f1c9a7d2b64
Revises: 7a9c98461b20
Create Date: 2026-11-02 09:20:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3f1c9a7d2b64"
down_revision = "7a9c98461b20"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("google_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("avatar_url", sa.String(length=512), nullable=True))
        batch_op.create_index("ix_users_google_id", ["google_id"], unique=True)


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_google_id")
        batch_op.drop_column("avatar_url")
        batch_op.drop_column("google_id")
