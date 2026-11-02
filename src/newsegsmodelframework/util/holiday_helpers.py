"""Helpers for finding public holidays.
"""
import os
from functools import lru_cache

import pandas as pd

from newsegsmodelframework import STATICDATA

_loaded_holidays = {}

@lru_cache
def get_holiday_df(start_year, end_year, holiday_country = 'GB', holiday_subdiv = 'WLS'):
    """Dataframe of the holidays in a range of years, by day.

    For Great Britain the holidays are read from the parquet files in the `data` directory; otherwise they come from the `holidays` package. Cached.

    Args:
        start_year: First year.
        end_year: Last year.
        holiday_country: Country code of the holidays.
        holiday_subdiv: Subdivision code of the holidays.

    Returns:
        Dataframe indexed by day, flagging holidays.
    """
    if holiday_country == 'GB':
        global _loaded_holidays
        hol_fn = 'gb_' + holiday_subdiv.lower() + '.parquet'
        raw_df = _loaded_holidays.get(hol_fn)
        if raw_df is None:
            raw_df = pd.read_parquet(os.path.join(STATICDATA, 'holidays', hol_fn))
            _loaded_holidays[hol_fn] = raw_df
        days = pd.date_range('{}-01-01'.format(start_year), '{}-01-01'.format(end_year + 1), freq = 'D', tz = 'utc')
        
        return raw_df.loc[days, :]
    else:
        import holidays
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