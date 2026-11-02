"""
Generates and derives constants to be re-used in rapid calculations.
"""
import os

import pandas as pd

from common import setup_script_env
setup_script_env()

from config import settings
from newsegsmodelframework import STATICDATA
lookup_dir = settings.get('SprakeDataLoc', STATICDATA / 'sprake_data')

from newsegsmodelframework.newsegsmodel.sprakemodel import SprakeModel
from newsegsmodelframework.newsegscs.newsegscs import get_consumption_meters
from newsegsmodelframework.newsegsstats.core import assign_year_index

def get_sprakemodel_appliance_consumption(mdl: SprakeModel):
    if mdl.consumption_storage.appliance_params.get('efficiency_reduction') != 0.0:
        mdl.consumption_storage.appliance_params['efficiency_reduction'] = 0.0
        mdl.consumption_storage.dirty = True
    
    if mdl.dirty:
        mdl.run()
    
    conr = mdl.get_consumption_storage_result()
    mtrs = get_consumption_meters(conr)

    n_units = mdl.consumption_storage.n_units

    mean_appliance_consumption = (
        mtrs
        .loc[:,['appliance_import']]
        .pipe(assign_year_index)
        .query('year_index >= 0')
        .groupby('year_index')
        .sum()
        .mean()
        .iloc[0]
    )
    mean_appliance_consumption = mean_appliance_consumption / float(n_units)

    return {
        'sprake_ref_appliance_consumption_annual': float(mean_appliance_consumption)
    }

def get_sprakemodel_expected_heating_degree_days():
    calibration_dd = pd.read_excel(
        os.path.join(
            lookup_dir,
            'calibration_heating_degree_days.xlsx'
        ),
        sheet_name = 'heating_degree_days',
        header = 0
    ).assign(timestamp = lambda df: df['timestamp'].dt.tz_localize(tz='utc'))

    return {
        'sprake_ref_hdd_per_year': float(calibration_dd['hdd_15_5'].sum())
    }

def get_sprakemodel_constants() -> dict:
    mdl = SprakeModel.from_none()

    consts = {}
    consts.update(get_sprakemodel_appliance_consumption(mdl))
    consts.update(get_sprakemodel_expected_heating_degree_days())

    return consts

def make_constants() -> dict:
    all_consts = {}
    all_consts['sprake_model'] = get_sprakemodel_constants()

    return all_consts

if __name__=='__main__':
    consts = make_constants()
    
    import os
    import json
    from pathlib import Path
    PACKAGEDIR = Path(__file__).parent.parent.absolute()

    pth = os.path.join(
        PACKAGEDIR,
        'src',
        'constants',
        'model_constants.json'
    )

    print(f'writing to: {pth}')

    with open(pth, 'w') as f:
        json.dump(consts, f)
