"""Helper functions for aligning timeseries with EV charging profile data."""

import os
from functools import lru_cache

import numpy as np
import pandas as pd

from newsegsmodelframework.util.holiday_helpers import get_holiday_df

from config import settings
from newsegsmodelframework import STATICDATA
lookup_dir = settings.get('SprakeDataLoc', STATICDATA / 'sprake_data')

# Profile data is the proportion of annual residential consumption for EV per period
# in periods of one hour through 2017
# https://smarter.energynetworks.org/projects/nia_ngso0021
# Notably, 2017 is not a leap year.
# Regardless, to make these data representative of weekly as well as yearly trend, they need characterisation
# Timestamp is at half hour within hour of observation
#PROFILE_DATA = pd.read_parquet(
#    os.path.join(
#        lookup_dir,
#        r'NG EV Charging Behaviour Study - Demand Profiles - V3 - External (11-04-2019 00-00-00).gzip'
#    )
#)                            

def characterise_dates_evprofile(
    datetimes,
    holiday_country = 'GB', 
    holiday_subdiv = 'WLS'
):
    """
    Assign variables to characterise a datetime series or DataFrame by ev charging averaging periods
    """
    if isinstance(datetimes, pd.DataFrame):
        if not 'datetime' in datetimes.columns:
            raise ValueError('Passed DataFrame must contain `datetime` column')
        oframe = datetimes
    else:
        oframe = pd.DataFrame({'datetime': pd.to_datetime(datetimes)})
    
    start_year = oframe['datetime'].iloc[0].year
    end_year = oframe['datetime'].iloc[-1].year
    hol_df = get_holiday_df(start_year, end_year, holiday_country, holiday_subdiv)


    # As we are going month by month, we will not use bank holidays as their own category
    # as the data are too sparse - will just roll them into the Sunday profile.
    oframe = (
        oframe
        .assign(
            datetime_day = lambda df: df['datetime'].dt.floor('D')
        )
        .set_index('datetime_day')
        .join(hol_df, how = 'left')
        .reset_index()
        .assign(
            month_n = lambda df: df['datetime'].dt.month,
            day_n = lambda df: df['datetime'].dt.day_of_week,
            is_sat = lambda df: df['day_n'] == 5,
            is_sun = lambda df: df['day_n'] == 6,
            is_bh = lambda df: np.logical_and(df['is_holiday'], np.logical_not(np.logical_or(df['is_sat'], df['is_sun']))),
            prof_day = lambda df: np.where(
                df['is_bh'], 'sun',
                np.where(
                    df['is_sun'], 'sun',
                    np.where(
                        df['is_sat'], 'sat',
                        'wd'
                    )
                )
            )
        )
    )            

    return oframe

# As England is by far the largest by EV ownership, use English holidays to 
# characterise profiles
def characterise_profile_data(
    profile_data:pd.DataFrame,
    holiday_country = 'GB',
    holiday_subdiv = 'ENG'
):
    
    return (
        profile_data.pipe(characterise_dates_evprofile, holiday_country, holiday_subdiv)
        .groupby(['start_day_seconds','end_day_seconds','month_n','prof_day'])
        ['Residential']
        .mean()
    )

#PROFILE_DATA_CHARACTERISED = characterise_profile_data(PROFILE_DATA).to_frame().reset_index()
PROFILE_DATA_CHARACTERISED = pd.read_parquet(
    os.path.join(
        lookup_dir,
        r'CHARACTERISED NG EV Charging Behaviour Study - Demand Profiles - V3 - External (11-04-2019 00-00-00).gzip'
    )
)  

# TODO: This function takes too long
def ev_profiles_for_time_spans(time_spans,
                               profile_data=PROFILE_DATA_CHARACTERISED):
    import sqlite3
    
    with sqlite3.connect(':memory:') as conn:
        profile_data.loc[:,['start_day_seconds','end_day_seconds',
                            'month_n', 'prof_day',
                            'Residential']].to_sql('profile_data', conn, index=False)
        time_spans.to_sql('time_spans', conn, index = False)

        qry = '''
        select
            time_spans.start_day_seconds start_day_seconds,
            time_spans.end_day_seconds end_day_seconds,
            profile_data.start_day_seconds prof_sds,
            profile_data.end_day_seconds prof_eds,
            profile_data.month_n month_n,
            profile_data.prof_day prof_day,
            profile_data.Residential consumption_rate
        from
            time_spans join profile_data on
            not(time_spans.end_day_seconds <= profile_data.start_day_seconds) and not(time_spans.start_day_seconds >= profile_data.end_day_seconds)
        '''

        df = pd.read_sql_query(qry, conn)\
            .assign(
                window_length = lambda df: (np.minimum(df['end_day_seconds'], df['prof_eds']) - np.maximum(df['start_day_seconds'], df['prof_sds']))/3600.0,
                consumption = lambda df: df['consumption_rate'] * df['window_length']
            ) \
            .groupby(['start_day_seconds', 'end_day_seconds','month_n','prof_day']) \
            ['consumption']\
            .sum()

        return df

# TODO: this is too slow
def get_ev_consumption(
    datetimes,
    annual_consumption:float = 2000.0,
    profile_data = PROFILE_DATA_CHARACTERISED,
    holiday_country = 'GB',
    holiday_subdiv = 'WLS'
):
    """
    Given a regular timeseries, get the profiled EV consumption between adjacent entries

    If spanning multiple days, midnight times must be present in the series
    """

    datetimes = pd.to_datetime(datetimes)
    if len(datetimes) < 2:
        raise ValueError("Consumption is between adjacent times, require at least 2")
    
    # Our datetimes are retrospective (i.e. are at the end of the interval).
    # In order to make sure they are assigned the correct elexon period (at midnight), we need to get the start
    # of the interval
    start_datetimes = pd.Series(datetimes).shift(1, fill_value=datetimes[0])
    oframe = (
        characterise_dates_evprofile(start_datetimes, holiday_country, holiday_subdiv)
        .rename(columns={'datetime':'start_datetime'})
        .assign(
            datetime = datetimes,
            end_day_seconds = lambda df: (df['datetime'] - df['datetime'].dt.floor('D')).dt.total_seconds(),
            start_day_seconds = lambda df: df['end_day_seconds'].shift(1, fill_value = df['end_day_seconds'].iloc[0]),
            time_delta = lambda df: df['datetime'] - df['datetime'].shift(1, fill_value=df['datetime'].iloc[0])
            )
        .assign(
            end_day_seconds = lambda df: df['start_day_seconds'] + df['time_delta'].dt.total_seconds()
        )

    )

    oframe = oframe.set_index(['start_day_seconds', 'end_day_seconds'])

    time_spans = oframe.index.unique().to_frame()

    working_profiles = ev_profiles_for_time_spans(time_spans, profile_data)

    oframe = oframe \
        .reset_index() \
        .set_index(['start_day_seconds','end_day_seconds','month_n','prof_day']) \
        .join(working_profiles) \
        .reset_index() \
        .assign(
            consumption = lambda df: annual_consumption * np.where(np.isnan(df['consumption']), 0.0, df['consumption'])
        )
    
    return oframe
