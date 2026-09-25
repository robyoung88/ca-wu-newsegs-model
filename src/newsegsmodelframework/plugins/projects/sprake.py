import json
import os
import pickle
from typing import cast

from newsegsmodelframework.newsegsmodel import newsegsmodel
from newsegsmodelframework.newsegsmodel import sprakemodel
from newsegsmodelframework.newsegsfinance import newsegsfinance
from newsegsmodelframework.newsegsfinance import sprakefinance
from newsegsmodelframework.newsegsvariable import variable
from newsegsmodelframework.newsegsmetamodel import newsegsmetamodel
import newsegsmodelframework.newsegsproject as newsegsproject

from newsegsmodelframework import PACKAGEDIR, STATICDATA
from newsegsmodelframework.plugins.registers import register_project_factory
_CONST_FILE = os.path.join(PACKAGEDIR, 'constants', 'model_constants.json')
with open(_CONST_FILE, 'r') as f:
    MODEL_CONSTANTS = json.load(f)

MODEL_TYPE = 'sprake'

def _create_default_model() -> newsegsmodel.NewsegsModel:
    # Load model
    with open(
        os.path.join(
            STATICDATA, 
            'sprakemodel-validation-config.pickle'
        ), 
    'rb') as f:
        mdl_conf = cast(newsegsmodel.NewsegsModel, pickle.load(f))
        mdl_conf.anonymise_ids()
    return mdl_conf
    #return sprakemodel.SprakeModel.from_dict(mdl_conf)

def _create_default_finance() -> newsegsfinance.NewsegsFinance:
    # Load finance configuration
    with open(
        os.path.join(
            STATICDATA,
            'sprakemodel-validation-finance-config.pickle'
        ),
    'rb') as f:
        fnc_conf = cast(newsegsfinance.NewsegsFinance, pickle.load(f))
        fnc_conf.anonymise_ids()
    return fnc_conf
    #return sprakefinance.SprakeFinance.from_dict(fnc_conf)

def _create_default_variables() -> list[variable.Variable]:
    with open(os.path.join(STATICDATA, 'sprake-variable-config.json')) as f:
        var_conf_list = json.load(f)
    def _make_var_from_dict(d):
        v = variable.variable_from_dict(d)
        v.id = v.generate_new_id()
        return v
    return [_make_var_from_dict(x) for x in var_conf_list]

@register_project_factory(MODEL_TYPE)
def sprake_project_factory():
    mdl = _create_default_model()
    fnc = _create_default_finance()
    # Do we want to randomise the ids? Leave as it at the moment,
    # but bear this in mind.
    fnc.set_model(mdl)

    variables = _create_default_variables()

    proj = newsegsproject.NewsegsProject(
        default_variables = variables,
        model_type = 'sprake',
        model_version = mdl.version
    )

    varids = proj.get_varids()
    mm = newsegsmetamodel.NewsegsMetaModel(
        mdl,
        fnc,
        variables = [proj.get_default_variable(x) for x in varids]
    )

    proj.metamodels.append(mm) # pyright: ignore[reportAttributeAccessIssue]

    return proj
