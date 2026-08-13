"""
Pre-compute the ev consumption for the Sprake model
"""
import pandas as pd

from common import setup_script_env
setup_script_env()

from newsegsmodelframework.newsegscs import ev_profiles

START_DT = pd.Timestamp('2005-01-01T00:00:00', tz='utc')
END_DT = pd.Timestamp('2015-01-01T00:00:00', tz='utc')

if __name__ == '__main__':
    consumption = ev_profiles.get_ev_consumption(
        pd.date_range(START_DT, END_DT, freq='h'),
        annual_consumption = 1.0
    )

    consumption.to_parquet(
        'data/ev_consumption_sprake.parquet'
    )
