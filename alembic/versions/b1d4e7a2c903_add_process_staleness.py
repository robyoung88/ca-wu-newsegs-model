"""Add process staleness

Revision ID: b1d4e7a2c903
Revises: 94a7c5e544c4
Create Date: 2026-11-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1d4e7a2c903'
down_revision: Union[str, Sequence[str], None] = '94a7c5e544c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('process_staleness',
    sa.Column('metamodel_id', sa.String(length=42), nullable=False),
    sa.Column('process', sa.String(length=16), nullable=False),
    sa.Column('inputs_changed_ns', sa.BigInteger(), nullable=True),
    sa.Column('last_run_ns', sa.BigInteger(), nullable=True),
    sa.PrimaryKeyConstraint('metamodel_id', 'process')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('process_staleness')
