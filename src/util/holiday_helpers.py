from functools import lru_cache

import pandas as pd

import holidays

@lru_cache
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