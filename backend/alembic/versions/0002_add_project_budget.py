"""add project monthly budget

Revision ID: 8f3a1d9c2b40
Revises: 1c20bbe6ba9c
Create Date: 2026-08-07 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f3a1d9c2b40'
down_revision: Union[str, None] = '1c20bbe6ba9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('monthly_budget_usd', sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('monthly_budget_usd')
