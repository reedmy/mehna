"""add external CV link to profiles

Revision ID: 8b2d4e6f1a90
Revises: 3f1c9a7d2b64
Create Date: 2026-11-02 12:05:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "8b2d4e6f1a90"
down_revision = "3f1c9a7d2b64"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("profiles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("cv_url", sa.String(length=512), nullable=True))


def downgrade():
    with op.batch_alter_table("profiles", schema=None) as batch_op:
        batch_op.drop_column("cv_url")
