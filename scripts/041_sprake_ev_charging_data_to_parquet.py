"""
Save out the ev charging profile data to parquet to speed up processing
"""
import os

import pandas as pd

from common import setup_script_env
setup_script_env()

from config import settings
lookup_dir = settings.get('SprakeDataLoc')

PROFILE_DATA = (
    pd.read_excel(
        os.path.join(
            lookup_dir,
            r'NG EV Charging Behaviour Study - Demand Profiles - V3 - External (11-04-2019 00-00-00).xlsx'
        ),
        sheet_name='GB Level Profile',
        header = 22,
        usecols=[0,2])
    .rename(columns={'Timestamp':'datetime'})  
    .assign(
        start_day_seconds = lambda df:  (df['datetime'] - df['datetime'].dt.floor('D')).dt.total_seconds() - 1800, 
        end_day_seconds = lambda df:  (df['datetime'] - df['datetime'].dt.floor('D')).dt.total_seconds() + 1800
    )
)

PROFILE_DATA.to_parquet(
    os.path.join(
        lookup_dir,
        r'NG EV Charging Behaviour Study - Demand Profiles - V3 - External (11-04-2019 00-00-00).gzip'
    ),
    compression = 'gzip'
)
