"""Project plugin for the `sprakeloc` model type.

Registers `sprakeloc_project_factory`, which creates a project of configurations of the Sprake 
Location-Aware Newsegs Model
"""

import json
import os
import pickle
from typing import cast

from newsegsmodelframework.core.trackeddata import RevisionNotifierMixin
from newsegsmodelframework.newsegsfinance.newsegsfinance import NewsegsFinance
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsmodel.newsegsmodel import NewsegsModel

from newsegsmodelframework import PACKAGEDIR, STATICDATA
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsvariable.variable import Variable, variable_from_dict
from newsegsmodelframework.plugins.registers import register_project_factory


MODEL_TYPE = 'sprakeloc'

def _reset_revision(comp):
    comp.reset_revision(chain = True)

def _create_default_model() -> NewsegsModel:
    # Load model
    with open(
        os.path.join(
            STATICDATA, 
            'sprakeloc-model-default-config.pickle'
        ), 'rb'
    ) as f:
        mdl_conf = cast(NewsegsModel, pickle.load(f))
    
    mdl_conf.anonymise_ids()
    _reset_revision(mdl_conf)
    mdl_conf.generation.generator.chain_syncronise()

    return mdl_conf

def _create_default_finance() -> NewsegsFinance:
    # Load finance configuration
    with open(
        os.path.join(
            STATICDATA,
            'sprakeloc-finance-default-config.pickle'
        ),
    'rb') as f:
        fnc_conf = cast(NewsegsFinance, pickle.load(f))
        fnc_conf.anonymise_ids()
        _reset_revision(fnc_conf)
    return fnc_conf

def _create_default_variables() -> list[Variable]:
    with open(os.path.join(STATICDATA, 'sprakeloc-variable-default-config.json')) as f:
        var_conf_list = json.load(f)
    def _make_var_from_dict(d):
        v = variable_from_dict(d)
        v.id = v.generate_new_id()
        _reset_revision(v)
        return v
    return [_make_var_from_dict(x) for x in var_conf_list]

@register_project_factory(MODEL_TYPE)
def sprake_project_factory():
    """Create a project of the Sprake Location-Aware model.

    The project has one metamodel, of the Sprake NewSEGS Energy Model and finance model loaded from the
    validated configurations in the `data` directory, with the default variables of the Sprake model.
    Notifications of revision are disabled while it is built so that the project starts with no modifications.

    Returns:
        The project.
    """
    prevstate = RevisionNotifierMixin._set_notification_state('disabled')
    try:
        mdl = _create_default_model()
        fnc = _create_default_finance()
        # Do we want to randomise the ids? Leave as it at the moment,
        # but bear this in mind.
        fnc.set_model(mdl)

        variables = _create_default_variables()

        proj = NewsegsProject(
            default_variables = variables,
            model_type = 'sprakeloc',
            model_version = mdl.version
        )

        varids = proj.get_varids()
        mm = NewsegsMetaModel(
            mdl,
            fnc,
            variables = [proj.get_default_variable(x) for x in varids]
        )
        _reset_revision(mm)

        proj.metamodels.append(mm) # pyright: ignore[reportAttributeAccessIssue]

        _reset_revision(proj)
    finally:
        RevisionNotifierMixin._set_notification_state(prevstate)

    return proj
