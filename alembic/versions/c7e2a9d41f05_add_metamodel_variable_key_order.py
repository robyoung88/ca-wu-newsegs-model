"""Add metamodel variable key order

Revision ID: c7e2a9d41f05
Revises: b1d4e7a2c903
Create Date: 2026-11-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e2a9d41f05'
down_revision: Union[str, Sequence[str], None] = 'b1d4e7a2c903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing rows are left null: their metamodels keep the order in which they were recovered before
    op.add_column('metamodel_variables', sa.Column('key_order', sa.Integer(), nullable=True))
    op.add_column('snapshot_metamodel_variables', sa.Column('key_order', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('snapshot_metamodel_variables') as batch_op:
        batch_op.drop_column('key_order')
    with op.batch_alter_table('metamodel_variables') as batch_op:
        batch_op.drop_column('key_order')
