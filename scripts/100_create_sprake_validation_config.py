"""
Set up a Sprake model per the external validation model, then save out the config as json.
"""
import json

from common import setup_script_env
setup_script_env()
from util import jsonfuncs

from newsegsmodel import sprakemodel

if __name__ == '__main__':
    mdl = sprakemodel.SprakeModel.from_none()
    mdl.generation.generator.generators[0].set_nameplate_capacity(200.)
    mdl.generation.generator.generators[1].set_nameplate_capacity(200.)
    mdl.consumption_storage.storage_params['storage_capacity'] = 4000.
    mdl.consumption_storage.spaceheat_params['hlp'] = 0.3
    mdl.consumption_storage.ev_per_unit = 0.2

    d1 = mdl.to_dict()
    with open('data/sprakemodel-validation-config.json', 'w') as f:
        json.dump(d1, f, cls = jsonfuncs.NumpyEncoder, sort_keys=False, indent=4)
