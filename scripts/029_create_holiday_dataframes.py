"""
Pre-generate relevant holiday dataframes.

As the holiday library is so heavy, makes sense to just create these off the bat
"""

import pandas as pd

import holidays

from common import setup_script_env
setup_script_env()

MIN_YEAR = 1980
MAX_YEAR = 2100

def get_holiday_df(start_year, end_year, holiday_country = 'GB', holiday_subdiv = 'WLS'):
    hols = holidays.country_holidays(holiday_country, holiday_subdiv)
    days = pd.date_range('{}-01-01'.format(start_year), '{}-01-01'.format(end_year + 1), freq = 'D', tz = 'utc')
    hol_df = (
        pd.DataFrame({'datetime_day': days})
        .assign(
            is_holiday = lambda df: df.apply(lambda rw: rw['datetime_day'] in hols, axis=1)
        )
        .set_index('datetime_day')
    )
    return hol_df

if __name__ == '__main__':
    gb_wls = get_holiday_df(MIN_YEAR, MAX_YEAR, 'GB', 'WLS')
    gb_wls.to_parquet('data/holidays/gb_wls.parquet')
    gb_eng = get_holiday_df(MIN_YEAR, MAX_YEAR, 'GB', 'ENG')
    gb_eng.to_parquet('data/holidays/gb_eng.parquet')
    gb_sct = get_holiday_df(MIN_YEAR, MAX_YEAR, 'GB', 'SCT')
    gb_sct.to_parquet('data/holidays/gb_sct.parquet')
    gb_nir = get_holiday_df(MIN_YEAR, MAX_YEAR, 'GB', 'NIR')
    gb_nir.to_parquet('data/holidays/gb_nir.parquet')
