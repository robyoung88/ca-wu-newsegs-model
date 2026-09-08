"""
Set up a Sprake model per the external validation model, then save out the config as json.
"""
import json
import pickle

from common import setup_script_env
setup_script_env()
from newsegsmodelframework.util import jsonfuncs

from newsegsmodelframework.newsegsmodel import sprakemodel

if __name__ == '__main__':
    mdl = sprakemodel.SprakeModel.from_none()
    mdl.generation.wind_capacity = 200.
    mdl.generation.pv_capacity = 200.
    mdl.consumption_storage.storage_capacity = 4000.
    mdl.consumption_storage.hlp = 0.3
    mdl.consumption_storage.ev_per_unit = 0.2

    d1 = mdl.to_dict()
    with open('data/sprakemodel-validation-config.json', 'w') as f:
        json.dump(d1, f, cls = jsonfuncs.NumpyEncoder, sort_keys=False, indent=4)

    with open('data/sprakemodel-validation-config.pickle', 'wb') as f:
        pickle.dump(mdl, f)
    

