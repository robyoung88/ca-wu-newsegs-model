"""Provides table definitions for application"""

import datetime
import uuid6

import sqlalchemy as sa
from sqlalchemy import event as sa_event

L_VARIABLE_UID = 38
L_COMPONENT_UID = 42

def clone_columns_except_pk(table: sa.Table):
    """Clones all columns from an existing table excluding primary keys and foreign keys."""
    cloned = []
    for col in table.columns:
        if not col.primary_key and not col.foreign_keys:
            cloned.append(
                sa.Column(
                    col.name,
                    col.type,
                    nullable=col.nullable,
                    default=col.default,
                    server_default=col.server_default,
                )
            )
    return cloned

get_uuid7 = lambda: str(uuid6.uuid7())

metadata = sa.MetaData()

# -----------------------------------------------------------------------------
# Snapshots
# -----------------------------------------------------------------------------

snapshots = sa.Table(
    'snapshots',
    metadata,
    sa.Column('snapshot_id', sa.Integer, primary_key = True, autoincrement = True),
    sa.Column('project_id', sa.String(L_VARIABLE_UID), sa.ForeignKey('projects.id')),
    sa.Column('label', sa.String, nullable = False),
    sa.Column('created_at', sa.DateTime, nullable = False, default = sa.func.current_timestamp())
)


# -----------------------------------------------------------------------------
# Variable Configurations
# -----------------------------------------------------------------------------

variable_configs = sa.Table(
    'variable_configs',
    metadata,
    sa.Column('id', sa.String(L_VARIABLE_UID), primary_key = True), # NB - this is the prefix+uuid of the object
    sa.Column('varid', sa.String), # The variable type identifier - e.g. {modelsection}.{key}.{subindex}
    sa.Column('revision', sa.Integer), # The revision number - incremented on modification of _config
    sa.Column('component_type', sa.String),
    sa.Column('payload', sa.String),
    sa.Column('label', sa.String, nullable = True),
    sa.Column('retain', sa.Boolean, default = False),
)

snapshot_variable_configs = sa.Table(
    'snapshot_variable_configs',
    metadata,
    sa.Column('snapshot_id', sa.Integer, sa.ForeignKey('snapshots.snapshot_id'), primary_key = True),
    sa.Column('id', sa.String(L_VARIABLE_UID), primary_key = True),
    *clone_columns_except_pk(variable_configs)
)


# -----------------------------------------------------------------------------
# Component Configurations
# -----------------------------------------------------------------------------

component_configs = sa.Table(
    'component_configs',
    metadata,
    sa.Column('id', sa.String(L_COMPONENT_UID), primary_key = True), # NB - this is the prefix+uuid of the object and limits the prefix to 5 chars
    sa.Column('component_type', sa.String),
    sa.Column('component_class', sa.String),
    sa.Column('component_version', sa.String),
    sa.Column('payload', sa.String),
    sa.Column('revision', sa.Integer, default = 0),
    sa.Column('last_result_id', sa.Integer, nullable = True),
    sa.Column('label', sa.String, nullable = True),
    sa.Column('retain', sa.Boolean, default = False),
)

snapshot_component_configs = sa.Table(
    'snapshot_component_configs',
    metadata,
    sa.Column('snapshot_id', sa.Integer, sa.ForeignKey('snapshots.snapshot_id'), primary_key = True),
    sa.Column('id', sa.String(L_COMPONENT_UID), primary_key = True),
    *clone_columns_except_pk(component_configs)
)


# -----------------------------------------------------------------------------
# Results
# -----------------------------------------------------------------------------

results = sa.Table(
    'results',
    metadata,
    sa.Column('result_id', sa.Integer, primary_key = True, autoincrement = True),
    sa.Column('component_config_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('component_configs.id')),
    sa.Column('run_id', sa.Integer), # No need to put a FK constraint on this, is for convenience only
    sa.Column('component_type', sa.String),
    sa.Column('component_class', sa.String),
    sa.Column('component_version', sa.String),
    sa.Column('component_config_revision', sa.Integer, default = 0),
    
    sa.Column('result_type', sa.String, nullable = False),
    sa.Column('result_file', sa.String),
    sa.Column('retain', sa.Boolean, default = False),
    sa.Column('created_at', sa.DateTime(), server_default = sa.func.now()),
)

snapshot_results = sa.Table(
    'snapshot_results',
    metadata,
    sa.Column('snapshot_id', sa.Integer, sa.ForeignKey('snapshots.snapshot_id'), primary_key = True),
    sa.Column('result_id', sa.Integer, primary_key = True),
    sa.Column('component_config_id', sa.String(L_COMPONENT_UID)),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'component_config_id'],
        ['snapshot_component_configs.snapshot_id', 'snapshot_component_configs.id']
    ),
    *clone_columns_except_pk(results)
)


# -----------------------------------------------------------------------------
# Energy Models (EM)
# -----------------------------------------------------------------------------

em_configs = sa.Table(
    'em_configs',
    metadata,
    sa.Column('id', sa.String(L_COMPONENT_UID), primary_key = True), # NB - this is the prefix+uuid of the object
    sa.Column('grid_config_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('component_configs.id')),
    sa.Column('generation_config_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('component_configs.id')),
    sa.Column('cs_config_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('component_configs.id')),
    sa.Column('modeldata_config_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('component_configs.id')),
    sa.Column('table_config_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('component_configs.id')),
    sa.Column('model_class', sa.String),
    sa.Column('model_version', sa.String),
    sa.Column('payload', sa.String),
    sa.Column('revision', sa.Integer, default = 0),
    sa.Column('label', sa.String, nullable = True),
    sa.Column('retain', sa.Boolean, default = False),
)

snapshot_em_configs = sa.Table(
    'snapshot_em_configs',
    metadata,
    sa.Column('snapshot_id', sa.Integer, sa.ForeignKey('snapshots.snapshot_id'), primary_key = True),
    sa.Column('id', sa.String(L_COMPONENT_UID), primary_key = True),
    sa.Column('grid_config_id', sa.String(L_COMPONENT_UID)),
    sa.Column('generation_config_id', sa.String(L_COMPONENT_UID)),
    sa.Column('cs_config_id', sa.String(L_COMPONENT_UID)),
    sa.Column('modeldata_config_id', sa.String(L_COMPONENT_UID)),
    sa.Column('table_config_id', sa.String(L_COMPONENT_UID)),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'grid_config_id'],
        ['snapshot_component_configs.snapshot_id', 'snapshot_component_configs.id']
    ),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'generation_config_id'],
        ['snapshot_component_configs.snapshot_id', 'snapshot_component_configs.id']
    ),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'cs_config_id'],
        ['snapshot_component_configs.snapshot_id', 'snapshot_component_configs.id']
    ),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'modeldata_config_id'],
        ['snapshot_component_configs.snapshot_id', 'snapshot_component_configs.id']
    ),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'table_config_id'],
        ['snapshot_component_configs.snapshot_id', 'snapshot_component_configs.id']
    ),
    *clone_columns_except_pk(em_configs),
)


# -----------------------------------------------------------------------------
# Finance Models (FM)
# -----------------------------------------------------------------------------

fm_configs = sa.Table(
    'fm_configs',
    metadata,
    sa.Column('id', sa.String(L_COMPONENT_UID), primary_key = True), # NB - this is the prefix+uuid of the object
    sa.Column('financedata_config_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('component_configs.id')),
    sa.Column('table_config_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('component_configs.id')),
    sa.Column('model_class', sa.String),
    sa.Column('model_version', sa.String),
    sa.Column('payload', sa.String),
    sa.Column('revision', sa.Integer, default = 0),
    sa.Column('label', sa.String, nullable = True),
    sa.Column('retain', sa.Boolean, default = False),
)

snapshot_fm_configs = sa.Table(
    'snapshot_fm_configs',
    metadata,
    sa.Column('snapshot_id', sa.Integer, sa.ForeignKey('snapshots.snapshot_id'), primary_key = True),
    sa.Column('id', sa.String(L_COMPONENT_UID), primary_key = True),
    sa.Column('financedata_config_id', sa.String(L_COMPONENT_UID)),
    sa.Column('table_config_id', sa.String(L_COMPONENT_UID)),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'financedata_config_id'],
        ['snapshot_component_configs.snapshot_id', 'snapshot_component_configs.id']
    ),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'table_config_id'],
        ['snapshot_component_configs.snapshot_id', 'snapshot_component_configs.id']
    ),
    *clone_columns_except_pk(fm_configs),
)


# -----------------------------------------------------------------------------
# Metamodels
# -----------------------------------------------------------------------------

metamodels = sa.Table(
    'metamodels',
    metadata,
    sa.Column('id', sa.String(L_COMPONENT_UID), primary_key = True), # NB - this is the prefix+uuid of the object
    sa.Column('em_config_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('em_configs.id')),
    sa.Column('fm_config_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('fm_configs.id')),
    sa.Column('table_config_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('component_configs.id')),
    sa.Column('payload', sa.String, default = '{}'),
    sa.Column('revision', sa.Integer, default = 0),
    sa.Column('label', sa.String, nullable = True),
    sa.Column('retain', sa.Boolean, default = False),
    sa.Column('lat', sa.Float, default = 53.0),
    sa.Column('lon', sa.Float, default = -3.0),
    sa.Column('n_units', sa.Float, default = 1.0)
)

snapshot_metamodels = sa.Table(
    'snapshot_metamodels',
    metadata,
    sa.Column('snapshot_id', sa.Integer, sa.ForeignKey('snapshots.snapshot_id'), primary_key = True),
    sa.Column('id', sa.String(L_COMPONENT_UID), primary_key = True),
    sa.Column('em_config_id', sa.String(L_COMPONENT_UID)),
    sa.Column('fm_config_id', sa.String(L_COMPONENT_UID)),
    sa.Column('table_config_id', sa.String(L_COMPONENT_UID)),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'em_config_id'],
        ['snapshot_em_configs.snapshot_id', 'snapshot_em_configs.id']
    ),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'fm_config_id'],
        ['snapshot_fm_configs.snapshot_id', 'snapshot_fm_configs.id']
    ),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'table_config_id'],
        ['snapshot_component_configs.snapshot_id', 'snapshot_component_configs.id']
    ),
    *clone_columns_except_pk(metamodels)
)


# -----------------------------------------------------------------------------
# Projects
# -----------------------------------------------------------------------------

projects = sa.Table(
    'projects',
    metadata,
    sa.Column('id', sa.String(L_COMPONENT_UID), primary_key = True), # NB - this is the prefix+uuid of the object
    sa.Column('dsa_component_config_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('component_configs.id')),
    sa.Column('psa_component_config_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('component_configs.id')),
    sa.Column('table_config_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('component_configs.id')),
    sa.Column('focussed_metamodel_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('metamodels.id')),
    sa.Column('model_type', sa.String, nullable = False),
    sa.Column('model_version', sa.String, nullable = False),
    sa.Column('payload', sa.String, default = '{}'),
    sa.Column('revision', sa.Integer, default = 0),

    # TODO: Implement these groups
    #sa.Column('read_group_id', sa.Integer, sa.ForeignKey('groups.group_id'))
    #sa.Column('write_group_id', sa.Integer, sa.ForeignKey('groups.group_id'))
    
    sa.Column('label', sa.String, nullable = True),
    sa.Column('retain', sa.Boolean, default = False),
    sa.Column('created_at', sa.DateTime(), server_default = sa.func.now()),
    sa.Column('modified_at', sa.DateTime(), default = datetime.datetime.now, onupdate = datetime.datetime.now),
    sa.Column('modified_order', sa.String(36), default = get_uuid7, onupdate = get_uuid7),
)

snapshot_projects = sa.Table(
    'snapshot_projects',
    metadata,
    sa.Column('snapshot_id', sa.Integer, sa.ForeignKey('snapshots.snapshot_id'), primary_key = True),
    sa.Column('id', sa.String(L_COMPONENT_UID), primary_key = True),
    sa.Column('dsa_component_config_id', sa.String(L_COMPONENT_UID)),
    sa.Column('psa_component_config_id', sa.String(L_COMPONENT_UID)),
    sa.Column('table_config_id', sa.String(L_COMPONENT_UID)),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'dsa_component_config_id'],
        ['snapshot_component_configs.snapshot_id', 'snapshot_component_configs.id']
    ),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'psa_component_config_id'],
        ['snapshot_component_configs.snapshot_id', 'snapshot_component_configs.id']
    ),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'table_config_id'],
        ['snapshot_component_configs.snapshot_id', 'snapshot_component_configs.id']
    ),
    *clone_columns_except_pk(projects)
)


# -----------------------------------------------------------------------------
# Project Metamodels (Junction Tables)
# -----------------------------------------------------------------------------

project_metamodels = sa.Table(
    'project_metamodels',
    metadata,
    sa.Column('project_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('projects.id'), primary_key = True),
    sa.Column('metamodel_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('metamodels.id'), primary_key = True),
    sa.Column('created_at', sa.DateTime, server_default = sa.func.now(), nullable = False,),
    sa.Column('created_order', sa.String(36), default = lambda: str(uuid6.uuid7()))
)

snapshot_project_metamodels = sa.Table(
    'snapshot_project_metamodels',
    metadata,
    sa.Column('snapshot_id', sa.Integer, sa.ForeignKey('snapshots.snapshot_id'), primary_key = True),
    sa.Column('project_id', sa.String(L_COMPONENT_UID), primary_key = True),
    sa.Column('metamodel_id', sa.String(L_COMPONENT_UID), primary_key = True),
    *clone_columns_except_pk(project_metamodels),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'project_id'],
        ['snapshot_projects.snapshot_id', 'snapshot_projects.id']
    ),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'metamodel_id'],
        ['snapshot_metamodels.snapshot_id', 'snapshot_metamodels.id']
    )
)

# -----------------------------------------------------------------------------
# Project Variables (Junction Tables)
# -----------------------------------------------------------------------------

project_variables = sa.Table(
    'project_variables',
    metadata,
    sa.Column('project_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('projects.id'), primary_key = True),
    sa.Column('variable_config_id', sa.String(L_VARIABLE_UID), sa.ForeignKey('variable_configs.id'), primary_key = True),
)

snapshot_project_variables = sa.Table(
    'snapshot_project_variables',
    metadata,
    sa.Column('snapshot_id', sa.Integer, sa.ForeignKey('snapshots.snapshot_id'), primary_key = True),
    sa.Column('project_id', sa.String(L_COMPONENT_UID), primary_key = True),
    sa.Column('variable_config_id', sa.String(L_VARIABLE_UID), primary_key = True),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'project_id'],
        ['snapshot_projects.snapshot_id', 'snapshot_projects.id']
    ),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'variable_config_id'],
        ['snapshot_variable_configs.snapshot_id', 'snapshot_variable_configs.id']
    )
)

# -----------------------------------------------------------------------------
# Metamodel Variables (Junction Tables)
# -----------------------------------------------------------------------------

metamodel_variables = sa.Table(
    'metamodel_variables',
    metadata,
    sa.Column('metamodel_id', sa.String(L_COMPONENT_UID), sa.ForeignKey('metamodels.id'), primary_key = True),
    sa.Column('variable_config_id', sa.String(L_VARIABLE_UID), sa.ForeignKey('variable_configs.id'), primary_key = True),
)

snapshot_metamodel_variables = sa.Table(
    'snapshot_metamodel_variables',
    metadata,
    sa.Column('snapshot_id', sa.Integer, sa.ForeignKey('snapshots.snapshot_id'), primary_key = True),
    sa.Column('metamodel_id', sa.String(L_COMPONENT_UID), primary_key = True),
    sa.Column('variable_config_id', sa.String(L_VARIABLE_UID), primary_key = True),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'metamodel_id'],
        ['snapshot_metamodels.snapshot_id', 'snapshot_metamodels.id']
    ),
    sa.ForeignKeyConstraint(
        ['snapshot_id', 'variable_config_id'],
        ['snapshot_variable_configs.snapshot_id', 'snapshot_variable_configs.id']
    )
)


# -----------------------------------------------------------------------------
# Runs
# -----------------------------------------------------------------------------

runs = sa.Table(
    'runs',
    metadata,
    sa.Column('run_id', sa.Integer, primary_key = True, autoincrement = True),
    sa.Column('project_id', sa.String(L_VARIABLE_UID), sa.ForeignKey('projects.id'), nullable = False),
    sa.Column('model_type', sa.String),
    sa.Column('request_id', sa.Integer),
    sa.Column('request_label', sa.String),
    sa.Column('request_class', sa.String),
    sa.Column('request_type', sa.String),
    sa.Column('payload', sa.String),
    sa.Column('status', sa.String),
    sa.Column('created_at', sa.DateTime, server_default = sa.func.now()),
    sa.Column('modified_at', sa.DateTime, default = datetime.datetime.now, onupdate = datetime.datetime.now), # Do not use server_onupdate, as not all backends can handle it.
    sa.Column('progress', sa.Float, default = 0.0),
    sa.Column('progress_message', sa.String, nullable = True),
    sa.Column('cancel_requested', sa.Boolean, default = False),
    sa.Column('children_spawned', sa.Boolean, default = False)
)

# -----------------------------------------------------------------------------
# Requests
# -----------------------------------------------------------------------------

requests = sa.Table(
    'requests',
    metadata,
    sa.Column('request_id', sa.Integer, primary_key = True, autoincrement = True),
    sa.Column('project_id', sa.String(L_VARIABLE_UID), sa.ForeignKey('projects.id'), nullable = False),
    sa.Column('request_class', sa.String),
    sa.Column('request_type', sa.String),
    sa.Column('payload', sa.String),
    sa.Column('dispatched', sa.Boolean, default = False),
    sa.Column('run_id', sa.Integer, nullable = True),
    sa.Column('retry_number', sa.Integer, default = 0),
    sa.Column('max_retries', sa.Integer, default = 5),
    sa.Column('completed', sa.Boolean, default = False)
)

# -----------------------------------------------------------------------------
# Sessions
# -----------------------------------------------------------------------------

sessions = sa.Table(
    'sessions',
    metadata,
    sa.Column('session_id', sa.String, primary_key = True),
    sa.Column('active_project_id', sa.String(L_VARIABLE_UID), sa.ForeignKey('projects.id')),
)

# -----------------------------------------------------------------------------
# Table creation
# -----------------------------------------------------------------------------

def create_all_tables(engine: sa.Engine):
    metadata.create_all(engine)
