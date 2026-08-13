import json
import os
from typing import MutableSequence

from newsegsmodelapp.newsegsbrowser import STATICDATA
from newsegsmodelframework.newsegsmodel import newsegsmodel
from newsegsmodelframework.newsegsmodel import sprakemodel
from newsegsmodelframework.newsegsfinance import newsegsfinance
from newsegsmodelframework.newsegsfinance import sprakefinance
from newsegsmodelframework.newsegsmetamodel import newsegsmetamodel
from newsegsmodelframework.newsegsvariable import variable

from newsegsmodelapp.newsegsbrowser import ROOTDIR
_CONST_FILE = os.path.join(ROOTDIR, 'constants', 'model_constants.json')
with open(_CONST_FILE, 'r') as f:
    MODEL_CONSTANTS = json.load(f)

def create_default_model() -> newsegsmodel.NewsegsModel:
    # Load model
    with open(
        os.path.join(
            STATICDATA, 
            'sprakemodel-validation-config.json'
        ), 
    'r') as f:
        mdl_conf = json.load(f)
    return sprakemodel.SprakeModel.from_dict(mdl_conf)

def create_default_finance() -> newsegsfinance.NewsegsFinance:
    # Load finance configuration
    with open(
        os.path.join(
            STATICDATA,
            'sprakemodel-validation-finance-config.json'
        ),
    'r') as f:
        fnc_conf = json.load(f)
    
    return sprakefinance.SprakeFinance.from_dict(fnc_conf)

def create_default_variables() -> list[variable.Variable]:
    with open(os.path.join(STATICDATA, 'sprake-variable-config.json')) as f:
        var_conf_list = json.load(f)
    return [variable.variable_from_dict(x) for x in var_conf_list]
