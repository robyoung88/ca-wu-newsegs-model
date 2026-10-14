"""
Pre-characterise the ev charging profile data
"""
import os

import pandas as pd

from common import setup_script_env
setup_script_env()

from newsegsmodelframework.newsegscs import ev_profiles

from config import settings
from newsegsmodelframework import STATICDATA
lookup_dir = settings.get('SprakeDataLoc', STATICDATA / 'sprake_data')

if __name__ == '__main__':
    PROFILE_DATA = pd.read_parquet(
        os.path.join(
            lookup_dir,
            r'NG EV Charging Behaviour Study - Demand Profiles - V3 - External (11-04-2019 00-00-00).gzip'
        )
    )      

    PROFILE_DATA_CHARACTERISED = ev_profiles.characterise_profile_data(PROFILE_DATA).to_frame().reset_index()

    PROFILE_DATA_CHARACTERISED.to_parquet(
        os.path.join(
            lookup_dir,
            r'CHARACTERISED NG EV Charging Behaviour Study - Demand Profiles - V3 - External (11-04-2019 00-00-00).gzip'
        ),
        compression = 'gzip'
    )
