"""Functions for interacting with newsegs projects."""
from functools import reduce
import json
from operator import iconcat
from typing import Any


from newsegsmodelframework.core.newsegscomponent import NewsegsComponent
from newsegsmodelframework.core.newsegsmodelinterface import NewsegsModelInterface
from newsegsmodelframework.core.newsegsfinanceinterface import NewsegsFinanceInterface
from newsegsmodelframework.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsproject import NewsegsProject

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
        dsa_component_config_id = proj.dsa_config.id,
        psa_component_config_id = proj.psa_config.id,
        table_config_id = proj.table_config.id,
        focussed_metamodel_id = proj.metamodel_ids[proj.get_focussed_metamodel_index()]
    )
    odict['payload'] = proj.json_dumps()
    
    return odict


# -----------------------------------------------------------------------------
# Metamodels
# -----------------------------------------------------------------------------
# region SAVE
def metamodel_to_raw_table_data(
    metamodel: NewsegsMetaModel
) -> dict:
    """
    Convert metamodel to a dictionary representation
    """
    odict = dict(
        id = metamodel.id,
        revision = metamodel.revision,
        label = metamodel.name,
        location = json.dumps(metamodel.model.location.to_dict()),
        lat = metamodel.model.location.lat,
        lon = metamodel.model.location.lon,
        em_config_id = metamodel.model.id,
        fm_config_id = metamodel.finance.id,
        table_config_id = metamodel.table_config.id,
    )
    if hasattr(metamodel.model.consumption_storage ,'n_units'):
        odict['n_units'] = metamodel.model.consumption_storage.n_units # pyright: ignore[reportAttributeAccessIssue]

    odict['payload'] = metamodel.json_dumps()
    
    return odict

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
        model_type = energy_model.model_type,
        revision = energy_model.revision,        
        label = energy_model.name,
        grid_config_id = energy_model.grid.id,
        generation_config_id = energy_model.generation.id,
        cs_config_id = energy_model.consumption_storage.id,
        modeldata_config_id = energy_model.model_data.id,
        table_config_id = energy_model.table_config.id
    )
    # Additional configuration needs to be implementation-specific, and might be things like
    # the default timestep. For now, let's use the already defined to_dict method
    odict['payload'] = energy_model.json_dumps()

    return odict


# -----------------------------------------------------------------------------
# Finance Model Configurations
# -----------------------------------------------------------------------------
# region SAVE
def finance_model_to_raw_table_data(
    finance_model: NewsegsFinanceInterface
) -> dict:
    """
    Convert a finance model to a dictionary representation without foreign keys.
    """
    odict: dict[str, Any] = dict(
        id = finance_model.id,
        model_class = finance_model.__class__.__name__,
        model_version = finance_model.version,
        revision = finance_model.revision,
        label = finance_model.name,
        financedata_config_id = finance_model.finance_data.id,
        table_config_id = finance_model.table_config.id,
    )

    odict['payload'] = finance_model.json_dumps()

    return odict

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
        label = component.name,
    )

    odict['payload'] = component.json_dumps()

    #if hasattr(component, '_component_config_id'):
    #    odict['component_config_id'] = component._module_config_id # pyright: ignore[reportAttributeAccessIssue]

    return odict
