"""
Save out the elexon profile data to parquet to speed up processing
"""
import os

import numpy as np
import pandas as pd

from common import setup_script_env
setup_script_env()

from config import settings
lookup_dir = settings.get('SprakeDataLoc')

if __name__ == '__main__':
    PROFILE_DATA = (
        pd.read_excel(
            os.path.join(
                lookup_dir, 
                r"Average_Profiling_data_201314_evaluated@10yearNET_v1.0.xlsx"
            ),
            sheet_name="Average Profile Class data",
            header=2, nrows=48, # For Profile 1
            dtype={'Settlement period':str}
        )
        .assign(
            **{'Settlement period': lambda df: pd.to_timedelta(df['Settlement period']),
                'end_day_seconds': lambda df: df['Settlement period'].dt.total_seconds()}
        )
        .assign(
            # Because these periods are retrospective, we end at midnight and a 0. Convert it to a 24
            end_day_seconds = lambda df: np.where(df['end_day_seconds']==0.0, 24.0*3600.0, df['end_day_seconds']),
            start_day_seconds = lambda df: df['end_day_seconds'].shift(1, fill_value = 0.0)
        )
        .melt(
            id_vars=['Settlement period','start_day_seconds','end_day_seconds'],
            var_name="profile",value_name="consumption_rate")
        .assign(
            split_prof = lambda df: df['profile'].str.split(" "),
            elexon_season = lambda df: df.apply(lambda rw: rw['split_prof'][0].lower(), axis=1),
            elexon_day = lambda df: df.apply(lambda rw: rw['split_prof'][1].lower(), axis=1),
        )
        .loc[:, ['start_day_seconds', 'end_day_seconds', 'elexon_season', 'elexon_day', 'consumption_rate']]
    )

    PROFILE_DATA.to_parquet(
        os.path.join(
            lookup_dir,
            r'Average_Profiling_data_201314_evaluated@10yearNET_v1.0.gzip'
        ),
        compression = 'gzip'
    )
