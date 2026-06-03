import json
import os

from src.newsegsbrowser import STATICDATA
from src.newsegsmodel import newsegsmodel
from src.newsegsmodel import sprakemodel
from src.newsegsfinance import newsegsfinance
from src.newsegsfinance import sprakefinance

from src.newsegsbrowser import ROOTDIR
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
