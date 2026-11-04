"""Move optimisation settings onto variables and a metamodel component

The bounds and marginal plot resolution of optimisation were held in a dictionary,
`optim_config['bounds'][varid]`, in the payload of a component of the project (the table
config, where the interface saved them; the dsa config, where the run looked for them).
They are now held by each variable, in the `optim_min`, `optim_max` and `optim_plot_intervals`
columns, which override the variable payload when a variable is loaded.

Variables record their `component_version`; it is left null for existing rows, which were
saved before versions were recorded (0.0.1).

The method and statistic of optimisation are now held by an `OptimComponent` of each
metamodel, referenced by `optim_config_id`. That is left null here: a metamodel without one is
given the default component when it is loaded, which is stored with its next upsert.

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

_projects = sa.table(
    'projects',
    sa.column('id'), sa.column('table_config_id'), sa.column('dsa_component_config_id'),
)
_snapshot_projects = sa.table(
    'snapshot_projects',
    sa.column('snapshot_id'), sa.column('id'), sa.column('table_config_id'), sa.column('dsa_component_config_id'),
)
_component_configs = sa.table(
    'component_configs',
    sa.column('id'), sa.column('payload'),
)
_snapshot_component_configs = sa.table(
    'snapshot_component_configs',
    sa.column('snapshot_id'), sa.column('id'), sa.column('payload'),
)
_project_variables = sa.table(
    'project_variables',
    sa.column('project_id'), sa.column('variable_config_id'),
)
_snapshot_project_variables = sa.table(
    'snapshot_project_variables',
    sa.column('snapshot_id'), sa.column('project_id'), sa.column('variable_config_id'),
)
_variable_configs = sa.table(
    'variable_configs',
    sa.column('id'), sa.column('varid'),
    sa.column('optim_min'), sa.column('optim_max'), sa.column('optim_plot_intervals'),
)
_snapshot_variable_configs = sa.table(
    'snapshot_variable_configs',
    sa.column('snapshot_id'), sa.column('id'), sa.column('varid'),
    sa.column('optim_min'), sa.column('optim_max'), sa.column('optim_plot_intervals'),
)


def _pop_bounds(conn, components, component_ids, snapshot_id = None) -> dict[str, dict]:
    """Remove `optim_config` from the payloads of the components, returning the bounds by varid.

    The table config is given last, so that what the interface saved takes precedence.
    """
    bounds = {}
    for component_id in component_ids:
        if component_id is None:
            continue
        where = components.c.id == component_id
        if snapshot_id is not None:
            where = sa.and_(where, components.c.snapshot_id == snapshot_id)
        payload = conn.execute(sa.select(components.c.payload).where(where)).scalar()
        if not payload:
            continue
        payload_dict = json.loads(payload)
        if 'optim_config' not in payload_dict:
            continue
        optim_config = payload_dict.pop('optim_config') or {}
        for varid, var_bounds in (optim_config.get('bounds') or {}).items():
            bounds.setdefault(varid, {}).update(var_bounds or {})
        conn.execute(components.update().where(where).values(payload = json.dumps(payload_dict)))
    return bounds


def _bound_values(var_bounds: dict) -> dict:
    """Column values for the saved bounds of a variable."""
    values = {}
    for key, column in (('lower', 'optim_min'), ('upper', 'optim_max')):
        if var_bounds.get(key) is not None:
            values[column] = json.dumps(var_bounds[key])
    intervals = var_bounds.get('intervals')
    if intervals is not None:
        try:
            values['optim_plot_intervals'] = int(intervals)
        except (TypeError, ValueError):
            pass
    return values


def _move_bounds(conn, projects, components, project_variables, variables, snapshot = False):
    """Write the bounds saved for each project to the variables of the project, and remove them from its components."""
    project_columns = [projects.c.id, projects.c.table_config_id, projects.c.dsa_component_config_id]
    if snapshot:
        project_columns.append(projects.c.snapshot_id)
    for row in conn.execute(sa.select(*project_columns)).fetchall():
        snapshot_id = row.snapshot_id if snapshot else None
        bounds = _pop_bounds(
            conn, components, (row.dsa_component_config_id, row.table_config_id), snapshot_id
        )
        for varid, var_bounds in bounds.items():
            values = _bound_values(var_bounds)
            if not values:
                continue
            # Bounds were held for the project, so apply to every variable of the project with the varid
            var_ids = sa.select(project_variables.c.variable_config_id).where(project_variables.c.project_id == row.id)
            where = sa.and_(variables.c.varid == varid, variables.c.id.in_(var_ids))
            if snapshot:
                var_ids = var_ids.where(project_variables.c.snapshot_id == snapshot_id)
                where = sa.and_(
                    variables.c.varid == varid,
                    variables.c.snapshot_id == snapshot_id,
                    variables.c.id.in_(var_ids),
                )
            conn.execute(variables.update().where(where).values(**values))


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
    for variables in (_variable_configs, _snapshot_variable_configs):
        conn.execute(variables.update().values(optim_plot_intervals = DEFAULT_PLOT_INTERVALS))
        # The lower bound was written from a class default of 0 that nothing used; unset, it uses the
        # minimum of the input field. Bounds that were saved are written below.
        conn.execute(variables.update().where(variables.c.optim_min == '0').values(optim_min = None))

    _move_bounds(conn, _projects, _component_configs, _project_variables, _variable_configs)
    _move_bounds(
        conn, _snapshot_projects, _snapshot_component_configs, _snapshot_project_variables,
        _snapshot_variable_configs, snapshot = True,
    )


def downgrade() -> None:
    """Downgrade schema.

    The bounds are left on the variables: they are not written back to the `optim_config`
    dictionary of the project, which is no longer read, so a downgraded app falls back to its
    default bounds.
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
