"""Functions for interacting with newsegs projects."""
from functools import reduce
import json
from operator import iconcat
from typing import Any, cast

import sqlalchemy as sa

from newsegsmodelframework.core.newsegscomponent import NewsegsComponent, TableConfigNewsegsComponent
from newsegsmodelframework.core.newsegsmodelinterface import NewsegsModelInterface
from newsegsmodelframework.core.newsegsmodule import NewsegsModule
from newsegsmodelframework.newsegscs.newsegscs import NewsegsCS
from newsegsmodelframework.newsegsfinance import NewsegsFinance
from newsegsmodelframework.newsegsfinance.newsegsfinance import NewsegsFinanceData
from newsegsmodelframework.newsegsgeneration.newsegsgeneration import NewsegsGeneration
from newsegsmodelframework.newsegsgrid.newsegsgrid import NewsegsGrid
from newsegsmodelframework.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsmodel import NewsegsModel
from newsegsmodelframework.newsegsmodel.newsegsmodel import NewsegsModelData
from newsegsmodelframework.newsegsproject import NewsegsProject
from newsegsmodelframework.core import find_constructor

from newsegsmodelapp.backend.db import tables as tbls
from newsegsmodelframework.newsegssensitivity.dsa import DSAComponent
from newsegsmodelframework.newsegssensitivity.psa import PSAComponent
from newsegsmodelframework.newsegsvariable.variable import Variable, variable_uid

def flatten(nested: list) -> list:
    return reduce(iconcat, nested, [])

# -----------------------------------------------------------------------------
# Projects
# -----------------------------------------------------------------------------
# region SAVE
def project_to_raw_table_data(
    proj: NewsegsProject
) -> dict:
    """
    Convert project to a dictionary representation without foreign keys
    """
    odict = dict(
        id = proj.id,
        model_type = proj.model_type,
        model_version = proj.model_version,
        label = proj.name,
        revision = proj.revision,
        uuid = proj.id
    )
    if hasattr(proj, '_project_id'):
        odict['project_id'] = proj._project_id # pyright: ignore[reportAttributeAccessIssue]
    return odict

def _get_metamodel_component_ids(
    metamodel: NewsegsMetaModel
) -> list[int]:
    return [
        metamodel.table_config._component_config_id, # pyright: ignore[reportAttributeAccessIssue]
        metamodel.model.model_data._component_config_id, # pyright: ignore[reportAttributeAccessIssue]
        metamodel.model.grid._component_config_id, # pyright: ignore[reportAttributeAccessIssue]
        metamodel.model.generation._component_config_id, # pyright: ignore[reportAttributeAccessIssue]
        metamodel.model.consumption_storage._component_config_id, # pyright: ignore[reportAttributeAccessIssue]
        metamodel.model.table_config._component_config_id, # pyright: ignore[reportAttributeAccessIssue]
        metamodel.finance.finance_data._component_config_id, # pyright: ignore[reportAttributeAccessIssue]
        metamodel.finance.table_config._component_config_id, # pyright: ignore[reportAttributeAccessIssue]
    ]

def _get_project_level_component_ids(
    project: NewsegsProject
) -> list[int]:
    return [
        project.dsa_config._component_config_id, # pyright: ignore[reportAttributeAccessIssue]
        project.psa_config._component_config_id, # pyright: ignore[reportAttributeAccessIssue]
        project.table_config._component_config_id, # pyright: ignore[reportAttributeAccessIssue]
    ]

def _get_all_component_ids(
    proj: NewsegsProject
) -> list[int]:
    rval = _get_project_level_component_ids(proj)

    for metamodel in proj.metamodels:
        rval.extend(_get_metamodel_component_ids(metamodel))
    return rval

def save_project_metamodels(
    proj: NewsegsProject,
    encon: sa.Engine | sa.Connection
) -> tuple[int, ...]:
    """Save the metamodels associated with a project.

    Note that this is NOT the same as setting the junction table entries for project-metamodels.
    See set_project_metamodels for that task.
    Args:
        proj (NewsegsProject): Project to save
        encon (sa.Engine | sa.Connection): SQLAlchemy engine or opened connection

    Returns:
        tuple[int, ...]: metamodel_id values entered into the metamodels table
    """
    return tuple(save_metamodel(x, encon) for x in proj.metamodels)

def save_project_children(
    proj: NewsegsProject,
    encon: sa.Engine | sa.Connection
) -> dict:
    odict = dict(
        dsa_component_config_id = save_component(proj.dsa_config, encon),
        psa_component_config_id = save_component(proj.psa_config, encon),
        table_config_id = save_component(proj.table_config, encon),
    )

    return odict

def save_project(
    proj: NewsegsProject,
    encon: sa.Engine | sa.Connection
) -> int:
    if isinstance(encon, sa.Engine):
        with encon.begin() as conn:
            return save_project(proj, conn)
    
    proj_data = project_to_raw_table_data(proj)
    metamodel_ids = save_project_metamodels(proj, encon)
    proj_data.update(save_project_children(proj, encon))

    def exists(project_id: int) -> bool:
        r = encon.execute(
            sa.select(tbls.projects.c.project_id)
            .where(tbls.projects.c.project_id == project_id)
        ).first()
        return r is not None

    project_id = proj_data.get('project_id')
    if project_id is not None and exists(project_id):
        proj_data.pop('project_id')
        encon.execute(
            tbls.projects.update()
            .where(tbls.projects.c.project_id == project_id)
            .values(**proj_data)
        )
    else:
        result = encon.execute(
            tbls.projects.insert()
            .values(**proj_data)
        )
        if not result or not result.inserted_primary_key:
            raise ValueError(f'Project not saved: {proj}')
        project_id = result.inserted_primary_key[0]
        proj._project_id = project_id # pyright: ignore[reportAttributeAccessIssue]

    set_project_metamodels(project_id, metamodel_ids, encon)

    # Save variables
    new_saved_vars = _save_project_variables(proj, encon)

    return project_id

def _load_project_data(
    project_id: int,
    conn: sa.Connection
):
    result = conn.execute(
        tbls.projects.select()
        .where(tbls.projects.c.project_id == project_id)
    ).fetchall()
    if len(result) < 1:
        raise ValueError(f'project not found: {project_id}')
    elif len(result) > 1:
        raise ValueError(f'Multiple projects found for id {project_id}')
    return result[0]


# region LOAD
def load_project(
    project_id: int,
    encon: sa.Engine | sa.Connection
) -> NewsegsProject:
    if isinstance(encon, sa.Engine):
        with encon.connect() as conn:
            return load_project(project_id, conn)

    proj_data = _load_project_data(project_id, encon)

    # Load metamodels
    metamodels = load_project_metamodels(project_id, encon)

    # Load components
    dsa_config = cast(DSAComponent, load_component(proj_data._mapping['dsa_component_config_id'], encon))
    psa_config = cast(PSAComponent, load_component(proj_data._mapping['psa_component_config_id'], encon))
    table_config = cast(TableConfigNewsegsComponent, load_component(proj_data._mapping['table_config_id'], encon))

    # Create the project
    project = NewsegsProject(
        metamodels, 
        #model_type = proj_data._mapping['model_type'],
        #model_version = proj_data._mapping['model_version'],
        dsa_config = dsa_config,
        psa_config = psa_config,
        table_config = table_config
    )
    project.id = proj_data._mapping['id']
    project._project_id = project_id # pyright: ignore[reportAttributeAccessIssue]

    # Load the variables (and assign to metamodels for now)
    proj_component_ids = _get_project_level_component_ids(project)
    proj_vars = flatten([load_component_variables(id, encon) for id in proj_component_ids])

    if proj_vars:
        raise NotImplementedError('Project has top-level variables - this feature is not yet supported.')
    
    for metamodel in project.metamodels:
        component_ids = _get_metamodel_component_ids(metamodel)
        metamodel_vars = flatten([load_component_variables(id, encon) for id in component_ids])
        if metamodel_vars:
            for v in metamodel_vars:
                metamodel.variables[v.id] = v

    return project


# -----------------------------------------------------------------------------
# Project - Metamodels Junction
# -----------------------------------------------------------------------------
# region SAVE
def set_project_metamodels(
    project_id: int,
    metamodel_ids: tuple[int, ...],
    encon: sa.Engine | sa.Connection
):
    if isinstance(encon, sa.Engine):
        with encon.begin() as conn:
            return set_project_metamodels(project_id, metamodel_ids, conn)

    # 1. Remove existing metamodels for project_id, if they exist
    # 2. Add all metamodel_ids for this project_id.
    encon.execute(
        tbls.project_metamodels.delete()
        .where(tbls.project_metamodels.c.project_id == project_id)
    )

    if metamodel_ids:
        encon.execute(
            tbls.project_metamodels.insert().values([
                {
                    'project_id': project_id,
                    'metamodel_id': metamodel_id,
                }
                for metamodel_id in metamodel_ids
            ])
        )

# region LOAD
def _load_metamodel_ids(
    project_id: int,
    conn: sa.Connection
) -> tuple[int, ...]:
    metamodel_ids = conn.execute(
        sa.select(tbls.project_metamodels.c.metamodel_id)
        .where(tbls.project_metamodels.c.project_id == project_id)
    ).fetchall()

    if metamodel_ids:
        metamodel_ids = tuple(x[0] for x in metamodel_ids)
        return metamodel_ids
    return tuple([])

def load_project_metamodels(
    project_id: int,
    encon: sa.Engine | sa.Connection
) -> tuple[NewsegsMetaModel, ...]:
    if isinstance(encon, sa.Engine):
        with encon.connect() as conn:
            return load_project_metamodels(project_id, conn)

    metamodel_ids = _load_metamodel_ids(project_id, encon)
    if not metamodel_ids:
        return tuple([])

    return tuple((load_metamodel(id, encon) for id in metamodel_ids))


# -----------------------------------------------------------------------------
# Variables
# -----------------------------------------------------------------------------
# region SAVE
_VARIABLE_MODEL_SECTION_MAP = {
    'model' : {
        'mod_gen': 'generation',
        'mod_cs._storage_params': 'cs',
        'mod_cs': 'cs',
        'mod_cs._spaceheat_params': 'cs',
        'mod_cs._dhw_params': 'cs',
        'mod_cs._appliance_params': 'cs',
        'mod_cs._ev_params': 'cs',
        '': 'modeldata',
    },
    'finance' : {
        '_unit_costs': 'financedata',
        '': 'financedata'
    }
}

def variable_to_raw_table_data(
    variable: Variable
) -> dict:
    model_sec = (
        _VARIABLE_MODEL_SECTION_MAP
        .get(variable.configuration_type, {})
        .get(variable.model_section, '')  # type: ignore
    )
    odict = dict(
        id = variable.id,
        varid = variable_uid(variable),
        component_type = model_sec,
        label = variable.name
    )

    odict['payload'] = variable.json_dumps()

    odict['variable_config_id'] = variable.uuid
    #if hasattr(variable, '_variable_config_id'):
    #    odict['variable_config_id'] = variable._variable_config_id # pyright: ignore[reportAttributeAccessIssue]

    return odict

def _get_variable_to_component_map(
    proj: NewsegsProject
) -> dict[str, dict[str, Any]]:
    variable_map = dict()
    for metamodel in proj.metamodels:
        def _model_sec_component_id(model_sec):
            match model_sec:
                case 'grid':
                    return metamodel.model.grid._component_config_id # pyright: ignore[reportAttributeAccessIssue]
                case 'generation':
                    return metamodel.model.generation._component_config_id # pyright: ignore[reportAttributeAccessIssue]
                case 'cs':
                    return metamodel.model.consumption_storage._component_config_id # pyright: ignore[reportAttributeAccessIssue]
                case 'modeldata':
                    return metamodel.model.model_data._component_config_id # pyright: ignore[reportAttributeAccessIssue]
                case 'financedata':
                    return metamodel.finance.finance_data._component_config_id # pyright: ignore[reportAttributeAccessIssue]
                case _:
                    raise ValueError(f'Unknown model section: {model_sec}')
                
        for variable in metamodel.variables.values():
            vid = variable.id
            model_sec = (
                _VARIABLE_MODEL_SECTION_MAP
                .get(variable.configuration_type, {})
                .get(variable.model_section, '')  # type: ignore
            )  # type: ignore
            if not vid in variable_map:
                variable_map[vid] = {
                    'variable': variable,
                    'components': [_model_sec_component_id(model_sec)]
                }
            else:
                variable_map[vid]['components'].append(_model_sec_component_id(model_sec))

    return variable_map

def _save_project_variables(
    proj: NewsegsProject,
    encon: sa.Engine | sa.Connection
) -> dict[str, int]:
    if isinstance(encon, sa.Engine):
        with encon.begin() as conn:
            return _save_project_variables(proj, conn)
    
    var_to_comp_map = _get_variable_to_component_map(proj)

    var_uuids = tuple(var_to_comp_map.keys())
    for id in var_uuids:
        var_to_comp_map[id]['data'] = variable_to_raw_table_data(var_to_comp_map[id]['variable'])

    variables_to_clear = [v['data'].pop('variable_config_id', None) for v in var_to_comp_map.values()]
    variables_to_clear = [v for v in variables_to_clear if v is not None]

    encon.execute(
        tbls.variable_configs.delete()
        .where(tbls.variable_configs.c.variable_config_id.in_(variables_to_clear))
    )

    insert_values = [var_to_comp_map[id]['data'] for id in var_uuids] 
    if insert_values:
        for idx, id in enumerate(var_uuids):
            # To avoid multirow insert, do this as a loop
            result = encon.execute(
                tbls.variable_configs.insert().values(insert_values[idx])
            )
            #var_to_comp_map[id]['variable'].uuid = result.inserted_primary_key[0] # pyright: ignore[reportOptionalSubscript]

    component_ids = _get_all_component_ids(proj)
    encon.execute(
        tbls.component_variables.delete()
        .where(tbls.component_variables.c.component_config_id.in_(component_ids))
    )

    insert_list = []
    for id in var_uuids:
        vardata = var_to_comp_map[id]
        insert_list.extend([
            {
                'variable_config_id': vardata['variable'].id, 
                'component_config_id': x
            } for x in vardata['components']
        ])

    if insert_list:
        encon.execute(
            tbls.component_variables.insert()
            .values(insert_list)
        )

    return {id: var_to_comp_map[id]['variable'].id for id in var_uuids}

# region LOAD
def load_variable(
    variable_config_id: str,
    encon: sa.Engine | sa.Connection
) -> Variable:
    if isinstance(encon, sa.Engine):
        with encon.connect() as conn:
            return load_variable(variable_config_id, conn)

    variable_data = _load_variable_data(variable_config_id, encon)

    constr_dict = json.loads(variable_data._mapping['payload'])
    variable = cast(
        Variable,
        find_constructor(constr_dict['constructor_class'], constr_dict['class'])(constr_dict)
    )

    #variable._variable_config_id = variable_config_id # pyright: ignore[reportAttributeAccessIssue]
    variable.id = variable_data._mapping['id']
    variable.name = variable_data._mapping['label']

    return variable

def _load_variable_data(
    variable_config_id: str,
    conn: sa.Connection
) -> sa.Row[Any]:
    result = conn.execute(
        tbls.variable_configs.select()
        .where(tbls.variable_configs.c.id == variable_config_id)
    ).fetchall()
    if len(result) < 1:
        raise ValueError(f'Variable not found: {variable_config_id}')
    elif len(result) > 1:
        raise ValueError(f'Multiple variables found for id {variable_config_id}')
    return result[0]


# -----------------------------------------------------------------------------
# Component-Variable Junction table
# -----------------------------------------------------------------------------
# region LOAD
def load_component_variables(
    component_config_id: int,
    encon: sa.Engine | sa.Connection
) -> tuple[Variable, ...]:
    if isinstance(encon, sa.Engine):
        with encon.connect() as conn:
            return load_component_variables(component_config_id, conn)

    variable_ids = _load_variable_ids(component_config_id, encon)
    if not variable_ids:
        return tuple([])

    return tuple((load_variable(id, encon) for id in variable_ids))

def _load_variable_ids(
    component_config_id: int,
    conn: sa.Connection
) -> tuple[str, ...]:
    variable_ids = conn.execute(
        sa.select(tbls.component_variables.c.variable_config_id)
        .where(tbls.component_variables.c.component_config_id == component_config_id)
    ).fetchall()

    if variable_ids:
        variable_ids = tuple(x[0] for x in variable_ids)
        return variable_ids
    return tuple([])

# -----------------------------------------------------------------------------
# Metamodels
# -----------------------------------------------------------------------------
# region SAVE
def metamodel_to_raw_table_data(
    metamodel: NewsegsMetaModel
) -> dict:
    """
    Convert metamodel to a dictionary representation without foreign keys
    """
    odict = dict(
        id = metamodel.id,
        revision = metamodel.revision,
        revision_string = metamodel.revision_string,
        label = metamodel.name,
        lat = metamodel.model.location.lat,
        lon = metamodel.model.location.lon,
    )
    if hasattr(metamodel.model.consumption_storage ,'n_units'):
        odict['n_units'] = metamodel.model.consumption_storage.n_units # pyright: ignore[reportAttributeAccessIssue]

    odict['payload'] = metamodel.json_dumps()
    
    return odict

def save_metamodel_children(
    metamodel: NewsegsMetaModel,
    encon: sa.Engine | sa.Connection
) -> dict[str, Any]:
    odict = dict(
        em_config_id = save_energy_model(metamodel.model, encon),
        fm_config_id = save_finance_model(metamodel.finance, encon),
        table_config_id = save_component(metamodel.table_config, encon),
    )
    return odict

def save_metamodel(
    metamodel: NewsegsMetaModel,
    encon: sa.Engine | sa.Connection,
) -> int:
    if isinstance(encon, sa.Engine):
        with encon.begin() as conn:
            return save_metamodel(metamodel, encon)

    mm_data = metamodel_to_raw_table_data(metamodel)
    mm_data.update(save_metamodel_children(metamodel, encon))

    metamodel_id = mm_data.get('metamodel_id')

    if metamodel_id is not None:
        existing = encon.execute(
            sa.select(tbls.metamodels.c.metamodel_id)
            .where(tbls.metamodels.c.metamodel_id == metamodel_id)
        ).first()
        if existing is not None:
            mm_data.pop('metamodel_id')
            encon.execute(
                tbls.metamodels.update()
                .where(tbls.metamodels.c.metamodel_id == metamodel_id)
                .values(**mm_data)
            )
            return metamodel_id

    result = encon.execute(
        tbls.metamodels.insert()
        .values(**mm_data)
    )
    if not result or not result.inserted_primary_key:
        raise ValueError(f'Metamodel not saved: {metamodel}')

    metamodel_id = result.inserted_primary_key[0]
    metamodel._metamodel_id = metamodel_id # pyright: ignore[reportAttributeAccessIssue]

    return metamodel_id

# region LOAD
def load_metamodel(
    metamodel_id: int,
    encon: sa.Engine | sa.Connection
) -> NewsegsMetaModel:
    if isinstance(encon, sa.Engine):
        with encon.connect() as conn:
            return load_metamodel(metamodel_id, conn)

    mm_data = _load_metamodel_data(metamodel_id, encon)

    mm_constr_args = {}
    em_config_id = mm_data._mapping.get('em_config_id')
    energy_model = None
    if em_config_id:
        energy_model = load_energy_model(em_config_id, encon)
        mm_constr_args['model'] = energy_model

    fm_config_id = mm_data._mapping.get('fm_config_id')
    finance_model = None
    if fm_config_id:
        finance_model = load_finance_model(fm_config_id, encon)
        mm_constr_args['finance'] = finance_model
    if finance_model and energy_model:
        finance_model.set_model(energy_model)

    table_config = cast(TableConfigNewsegsComponent, load_component(mm_data._mapping['table_config_id'], encon))
    mm_constr_args['table_config'] = table_config

    metamodel = NewsegsMetaModel(**mm_constr_args)

    metamodel._metamodel_id = metamodel_id # pyright: ignore[reportAttributeAccessIssue]
    metamodel.id = mm_data._mapping['id']
    metamodel._revision = mm_data._mapping['revision']
    metamodel.name = mm_data._mapping['label']

    # Set the submodules
    metamodel.table_config = table_config
    if energy_model:
        metamodel.model = energy_model
    if finance_model:
        metamodel.finance = finance_model

    return metamodel
    
def _load_metamodel_data(
    metamodel_id: int,
    conn: sa.Connection
) -> sa.Row[Any]:
    result = conn.execute(
        tbls.metamodels.select()
        .where(tbls.metamodels.c.metamodel_id == metamodel_id)
    ).fetchall()
    if len(result) < 1:
        raise ValueError(f'Metamodel not found: {metamodel_id}')
    elif len(result) > 1:
        raise ValueError(f'Multiple metamodels found for id {metamodel_id}')
    return result[0]

# -----------------------------------------------------------------------------
# Energy Models (EM)
# -----------------------------------------------------------------------------
# region SAVE
def energy_model_to_raw_table_data(
    energy_model: NewsegsModelInterface
) -> dict:
    """
    Convert an energy model to a dictionary representation without foreign keys
    """
    odict: dict[str, Any] = dict(
        id = energy_model.id,
        model_class = energy_model.__class__.__name__,
        model_version = energy_model.version,
        revision = energy_model.revision,
        revision_string = energy_model.revision_string,
        label = energy_model.name
    )
    # Additional configuration needs to be implementation-specific, and might be things like
    # the default timestep. For now, let's use the already defined to_dict method
    odict['payload'] = energy_model.json_dumps()

    return odict

def save_energy_model_children(
    energy_model: NewsegsModel,
    encon: sa.Engine | sa.Connection
) -> dict[str, Any]:
    return dict(
        grid_config_id = save_component(energy_model.grid, encon),
        generation_config_id = save_component(energy_model.generation, encon),
        cs_config_id = save_component(energy_model.consumption_storage, encon),
        modeldata_config_id = save_component(energy_model.model_data, encon),
        table_config_id = save_component(energy_model.table_config, encon),
    )
    
def save_energy_model(
    model: NewsegsModel,
    encon: sa.Engine | sa.Connection
) -> int:
    if isinstance(encon, sa.Engine):
        with encon.begin() as conn:
            return save_energy_model(model, encon)
    
    model_data = energy_model_to_raw_table_data(model)
    model_data.update(save_energy_model_children(model, encon))

    em_config_id = model_data.get('em_config_id')

    if em_config_id is not None:
        existing = encon.execute(
            sa.select(tbls.em_configs.c.em_config_id)
            .where(tbls.em_configs.c.em_config_id == em_config_id)
        ).first()
        if existing is not None:
            model_data.pop('em_config_id')
            encon.execute(
                tbls.em_configs.update()
                .where(tbls.em_configs.c.em_config_id == em_config_id)
                .values(**model_data)
            )
            return em_config_id

    result = encon.execute(
        tbls.em_configs.insert()
        .values(**model_data)
    )
    if not result or not result.inserted_primary_key:
        raise ValueError(f'Energy model not saved: {model}')

    em_config_id = result.inserted_primary_key[0]
    model._em_config_id = em_config_id # pyright: ignore[reportAttributeAccessIssue]

    return em_config_id

# region LOAD
def load_energy_model(
    em_config_id: int,
    encon: sa.Engine | sa.Connection
) -> NewsegsModel:
    if isinstance(encon, sa.Engine):
        with encon.connect() as conn:
            return load_energy_model(em_config_id, conn)

    em_config_data = _load_energy_model_data(em_config_id, encon)

    grid = cast(NewsegsGrid, load_component(em_config_data._mapping['grid_config_id'], encon))
    generation = cast(NewsegsGeneration, load_component(em_config_data._mapping['generation_config_id'], encon))
    consumption_storage = cast(NewsegsCS, load_component(em_config_data._mapping['cs_config_id'], encon))
    model_data = cast(NewsegsModelData, load_component(em_config_data._mapping['modeldata_config_id'], encon))
    table_config = cast(TableConfigNewsegsComponent, load_component(em_config_data._mapping['table_config_id'], encon))

    constr_dict = json.loads(em_config_data._mapping['config_payload'])
    model = cast(
        NewsegsModel,
        find_constructor(constr_dict['constructor_class'], constr_dict['class'])(constr_dict)
    )

    model._em_config_id = em_config_id # pyright: ignore[reportAttributeAccessIssue]
    model.id = em_config_data._mapping['id']
    model._revision = em_config_data._mapping['revision']
    model.name = em_config_data._mapping['label']

    # Set the submodules
    model.grid = grid
    grid.model = model

    model.generation = generation
    generation.model = model

    model.consumption_storage = consumption_storage
    consumption_storage.model = model

    model.model_data = model_data
    model.table_config = table_config

    return model

def _load_energy_model_data(
    em_config_id: int,
    conn: sa.Connection
) -> sa.Row[Any]:
    result = conn.execute(
        tbls.em_configs.select()
        .where(tbls.em_configs.c.em_config_id == em_config_id)
    ).fetchall()
    if len(result) < 1:
        raise ValueError(f'Energy Model Configuration not found: {em_config_id}')
    elif len(result) > 1:
        raise ValueError(f'Multiple energy model configurations found for {em_config_id}')
    return result[0]


# -----------------------------------------------------------------------------
# Finance Model Configurations
# -----------------------------------------------------------------------------
# region SAVE
def finance_model_to_raw_table_data(
    finance_model: NewsegsFinance
) -> dict:
    """
    Convert a finance model to a dictionary representation without foreign keys.
    """
    odict: dict[str, Any] = dict(
        id = finance_model.id,
        model_class = finance_model.__class__.__name__,
        model_version = finance_model.version,
        revision = finance_model.revision,
        revision_string = finance_model.revision_string,
        label = finance_model.name
    )

    odict['payload'] = finance_model.json_dumps()

    return odict

def save_finance_model_children(
    finance_model: NewsegsFinance,
    encon: sa.Engine | sa.Connection
) -> dict[str, Any]:
    return dict(
        financedata_config_id = save_component(finance_model.finance_data, encon),
        table_config_id = save_component(finance_model.table_config, encon),
    )

def save_finance_model(
    model: NewsegsFinance,
    encon: sa.Engine | sa.Connection
) -> int:
    if isinstance(encon, sa.Engine):
        with encon.begin() as conn:
            return save_finance_model(model, conn)

    model_data = finance_model_to_raw_table_data(model)
    model_data.update(save_finance_model_children(model, encon))

    fm_config_id = model_data.get('fm_config_id')
    if fm_config_id is not None:
        existing = encon.execute(
            sa.select(tbls.fm_configs.c.fm_config_id)
            .where(tbls.fm_configs.c.fm_config_id == fm_config_id)
        ).first()
        if existing is not None:
            model_data.pop('fm_config_id')
            encon.execute(
                tbls.fm_configs.update()
                .where(tbls.fm_configs.c.fm_config_id == fm_config_id)
                .values(**model_data)
            )
            return fm_config_id

    result = encon.execute(
        tbls.fm_configs.insert()
        .values(**model_data)
    )
    if not result or not result.inserted_primary_key:
        raise ValueError(f'Finance model not saved: {model}')

    fm_config_id = result.inserted_primary_key[0]
    model._fm_config_id = fm_config_id # pyright: ignore[reportAttributeAccessIssue]

    return fm_config_id

# region LOAD
def load_finance_model(
    fm_config_id: int,
    encon: sa.Engine | sa.Connection
) -> NewsegsFinance:
    if isinstance(encon, sa.Engine):
        with encon.connect() as conn:
            return load_finance_model(fm_config_id, conn)

    fm_config_data = _load_finance_model_data(fm_config_id, encon)

    finance_data = cast(NewsegsFinanceData, load_component(fm_config_data._mapping['financedata_config_id'], encon))
    table_config = cast(TableConfigNewsegsComponent, load_component(fm_config_data._mapping['table_config_id'], encon))

    constr_dict = json.loads(fm_config_data._mapping['config_payload'])
    model = cast(
        NewsegsFinance,
        find_constructor(constr_dict['constructor_class'], constr_dict['class'])(constr_dict)
    )

    model._fm_config_id = fm_config_id # pyright: ignore[reportAttributeAccessIssue]
    model.id = fm_config_data._mapping['id']
    model._revision = fm_config_data._mapping['revision']
    model.name = fm_config_data._mapping['label']

    # Set the submodules
    model.finance_data = finance_data
    model.table_config = table_config

    return model

def _load_finance_model_data(
    fm_config_id: int,
    conn: sa.Connection
) -> sa.Row[Any]:
    result = conn.execute(
        tbls.fm_configs.select()
        .where(tbls.fm_configs.c.fm_config_id == fm_config_id)
    ).fetchall()
    if len(result) < 1:
        raise ValueError(f'Finance Model Configuration not found: {fm_config_id}')
    elif len(result) > 1:
        raise ValueError(f'Multiple finance model configurations found for {fm_config_id}')
    return result[0]

# -----------------------------------------------------------------------------
# Module Configurations
# -----------------------------------------------------------------------------
# region SAVE
def component_to_raw_table_data(
    component: NewsegsComponent
) -> dict:
    """
    Convert a NewsegsModule to a dictionary without foreign keys"""
    odict: dict[str, Any] = dict(
        id = component.id,
        component_type = component.component_type,
        component_class = component.__class__.__name__,
        component_version = component.version,
        revision = component.revision,
        revision_string = component.revision_string,
        label = component.name,
    )

    odict['payload'] = component.json_dumps()

    #if hasattr(component, '_component_config_id'):
    #    odict['component_config_id'] = component._module_config_id # pyright: ignore[reportAttributeAccessIssue]

    return odict

def save_component(
    component: NewsegsComponent,
    encon: sa.Engine | sa.Connection
) -> int:
    if isinstance(encon, sa.Engine):
        with encon.begin() as conn:
            return save_component(component, conn)

    component_data = component_to_raw_table_data(component)
    component_config_id = component_data.get('component_config_id')
    if component_config_id is not None:
        existing = encon.execute(
            sa.select(tbls.component_configs.c.component_config_id)
            .where(tbls.component_configs.c.component_config_id == component_config_id)
        ).first()
        if existing is not None:
            component_data.pop('component_config_id')
            encon.execute(
                tbls.component_configs.update()
                .where(tbls.component_configs.c.component_config_id == component_config_id)
                .values(**component_data)
            )
            return component_config_id

    result = encon.execute(tbls.component_configs.insert().values(**component_data))
    if not result or not result.inserted_primary_key:
        raise ValueError(f'Component not saved: {component}')

    component_config_id = result.inserted_primary_key[0]
    component._component_config_id = component_config_id # pyright: ignore[reportAttributeAccessIssue]

    return component_config_id

# region LOAD
def load_component(
    component_config_id: int,
    encon: sa.Engine | sa.Connection
) -> NewsegsComponent:
    if isinstance(encon, sa.Engine):
        with encon.connect() as conn:
            return load_component(component_config_id, conn)

    component_data = _load_component_data(component_config_id, encon)
    component_dict = json.loads(component_data._mapping['config_payload'])
    component = cast(
        NewsegsComponent,
        find_constructor(component_dict['constructor_class'], component_dict['class'])(component_dict)
    )
    # Ensure that the component attributes match the database, not necessarily the payload
    component._component_config_id = component_config_id # pyright: ignore[reportAttributeAccessIssue]
    component.id = component_data._mapping['id']
    component._revision = component_data._mapping['revision']
    component.name = component_data._mapping['label']

    # Will trust to the component_type, component_class and component_version coming back correctly from the payload

    return component

def _load_component_data(
    component_config_id: int,
    conn: sa.Connection
) -> sa.Row[Any]:
    result = conn.execute(
        tbls.component_configs.select()
        .where(tbls.component_configs.c.component_config_id == component_config_id)
    ).fetchall()
    if len(result) < 1:
        raise ValueError(f'Component Configuration not found: {component_config_id}')
    elif len(result) > 1:
        raise ValueError(f'Multiple component configurations found for {component_config_id}')
    return result[0]
