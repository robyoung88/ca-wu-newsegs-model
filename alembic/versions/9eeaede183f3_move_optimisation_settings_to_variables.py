"""Move optimisation settings onto variables and a metamodel component

The bounds and marginal plot resolution of optimisation are now held by each variable, in the
`optim_min`, `optim_max` and `optim_plot_intervals` columns, which override the variable payload
when a variable is loaded. The method and statistic are held by an `OptimComponent` of each
metamodel, referenced by `optim_config_id`.

This is a breaking change: settings saved before it are discarded. Every variable starts with
unset bounds, which fall back to the limits of its input field, and the `optim_config` dictionary
that the interface saved in the project's table config is removed. `optim_config_id` is left null:
a metamodel without one is given the default component when it is loaded, which is stored with
its next upsert.

Variables record their `component_version`; it is left null for existing rows, which were
saved before versions were recorded (0.0.1).

Revision ID: 9eeaede183f3
Revises: c7e2a9d41f05
Create Date: 2026-11-04 12:00:00.000000

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9eeaede183f3'
down_revision: Union[str, Sequence[str], None] = 'c7e2a9d41f05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_PLOT_INTERVALS = 10


def _remove_optim_config(conn, table_name: str):
    """Remove the old `optim_config` dictionary from the payloads of the components that hold it."""
    components = sa.table(table_name, sa.column('payload'))
    for payload in conn.execute(
        sa.select(components.c.payload).where(components.c.payload.like('%"optim_config"%'))
    ).scalars().all():
        payload_dict = json.loads(payload)
        if payload_dict.pop('optim_config', None) is not None:
            conn.execute(
                components.update().where(components.c.payload == payload).values(payload = json.dumps(payload_dict))
            )


def upgrade() -> None:
    """Upgrade schema."""
    for table_name in ('variable_configs', 'snapshot_variable_configs'):
        op.add_column(table_name, sa.Column('component_version', sa.String(), nullable=True))
        op.add_column(table_name, sa.Column('optim_plot_intervals', sa.Integer(), nullable=True))

    with op.batch_alter_table('metamodels') as batch_op:
        batch_op.add_column(sa.Column('optim_config_id', sa.String(length=42), nullable=True))
        batch_op.create_foreign_key(
            'fk_metamodels_optim_config_id', 'component_configs', ['optim_config_id'], ['id']
        )
    with op.batch_alter_table('snapshot_metamodels') as batch_op:
        batch_op.add_column(sa.Column('optim_config_id', sa.String(length=42), nullable=True))
        batch_op.create_foreign_key(
            'fk_snapshot_metamodels_optim_config_id', 'snapshot_component_configs',
            ['snapshot_id', 'optim_config_id'], ['snapshot_id', 'id']
        )

    conn = op.get_bind()
    for table_name in ('variable_configs', 'snapshot_variable_configs'):
        variables = sa.table(table_name, sa.column('optim_min'), sa.column('optim_max'), sa.column('optim_plot_intervals'))
        # The old columns were written from class defaults that nothing used
        conn.execute(variables.update().values(
            optim_min = None, optim_max = None, optim_plot_intervals = DEFAULT_PLOT_INTERVALS,
        ))
    for table_name in ('component_configs', 'snapshot_component_configs'):
        _remove_optim_config(conn, table_name)


def downgrade() -> None:
    """Downgrade schema.

    The settings are not restored: a downgraded app falls back to its default bounds.
    """
    with op.batch_alter_table('snapshot_metamodels') as batch_op:
        batch_op.drop_constraint('fk_snapshot_metamodels_optim_config_id', type_='foreignkey')
        batch_op.drop_column('optim_config_id')
    with op.batch_alter_table('metamodels') as batch_op:
        batch_op.drop_constraint('fk_metamodels_optim_config_id', type_='foreignkey')
        batch_op.drop_column('optim_config_id')
    for table_name in ('snapshot_variable_configs', 'variable_configs'):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column('optim_plot_intervals')
            batch_op.drop_column('component_version')
