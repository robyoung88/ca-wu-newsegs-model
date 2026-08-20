import json
import os

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
            'sprakemodel-validation-config.json'
        ), 
    'r') as f:
        mdl_conf = json.load(f)
    return sprakemodel.SprakeModel.from_dict(mdl_conf)

def _create_default_finance() -> newsegsfinance.NewsegsFinance:
    # Load finance configuration
    with open(
        os.path.join(
            STATICDATA,
            'sprakemodel-validation-finance-config.json'
        ),
    'r') as f:
        fnc_conf = json.load(f)
    
    return sprakefinance.SprakeFinance.from_dict(fnc_conf)

def _create_default_variables() -> list[variable.Variable]:
    with open(os.path.join(STATICDATA, 'sprake-variable-config.json')) as f:
        var_conf_list = json.load(f)
    return [variable.variable_from_dict(x) for x in var_conf_list]

@register_project_factory(MODEL_TYPE)
def sprake_project_factory():
    mdl = _create_default_model()
    fnc = _create_default_finance()
    fnc.set_model(mdl)

    variables = _create_default_variables()

    mm = newsegsmetamodel.NewsegsMetaModel(mdl, fnc, variables)

    proj = newsegsproject.NewsegsProject([mm], MODEL_TYPE, mdl.version)
    return proj
