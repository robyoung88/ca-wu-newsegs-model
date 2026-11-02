"""Domestic hot water demand profiles.
"""
# Helper functions for aligning timeseries with DHW profile data

import os
import numpy as np
import pandas as pd

from config import settings
# Where to find dhw profile data
from newsegsmodelframework import STATICDATA
lookup_dir = settings.get('SprakeDataLoc', STATICDATA / 'sprake_data')

# NB - these data are prospective i.e. timestamp marks start of hour of consumption
PROFILE_DATA = pd.read_excel(os.path.join(lookup_dir,
                                          r"dhw_heating_profile_day.xlsx"),
                             sheet_name="DHW Profile",
                             header=0,
                             dtype={'timestamp':str}) \
                .assign(timestamp = lambda df: pd.to_timedelta(df['timestamp']),
                        start_day_seconds = lambda df: df['timestamp'].dt.total_seconds(),
                        end_day_seconds = lambda df: df['start_day_seconds'].shift(-1, fill_value = df['start_day_seconds'].iloc[-1] + (df['start_day_seconds'].iloc[1] - df['start_day_seconds'].iloc[0])))

def profiles_for_time_spans(time_spans, profile_data):
    """Fraction of the daily hot water heat demand in each of the time spans, from the profile.

    Args:
        time_spans: Dataframe of the start and end second of the day of each timestep.
        profile_data: Dataframe of the profile data.

    Returns:
        Dataframe of the fraction for each time span.
    """
    import sqlite3

    with sqlite3.connect(':memory:') as conn:
        PROFILE_DATA.loc[:,['start_day_seconds','end_day_seconds','proportion_dhw_heat']].to_sql('profile_data', conn, index = False)
        time_spans.to_sql('time_spans', conn, index = False)

        qry = '''
        select
            time_spans.start_day_seconds start_day_seconds,
            time_spans.end_day_seconds end_day_seconds,
            profile_data.start_day_seconds prof_sds,
            profile_data.end_day_seconds prof_eds,
            profile_data.proportion_dhw_heat heat
        from
            time_spans join profile_data on
            not(time_spans.end_day_seconds <= profile_data.start_day_seconds) and not(time_spans.start_day_seconds >= profile_data.end_day_seconds)
        '''

        df = pd.read_sql_query(qry, conn)\
            .assign(
                window_length = lambda df: (np.minimum(df['end_day_seconds'], df['prof_eds']) - np.maximum(df['start_day_seconds'], df['prof_sds']))/3600.0,
                fraction_dhw_heat = lambda df: df['heat'] * df['window_length']
            ) \
            .groupby(['start_day_seconds', 'end_day_seconds']) \
            ['fraction_dhw_heat']\
            .sum()
        
    return df

def get_dhw_energy_consumption(datetimes,
                               ref_daily_consumption:float=4.5,#kWh/day
                               seasonal_variance:float=0.2, #i.e. +- from reference
                               profile_data=PROFILE_DATA
                               ):
    
    """Energy consumption for domestic hot water at each timestep.

    The daily consumption varies seasonally about the reference by `seasonal_variance` and is distributed through the day by the profile.

    Args:
        datetimes: Datetimes at the start of each timestep.
        ref_daily_consumption: Reference daily hot water energy consumption of a household (kWh).
        seasonal_variance: Fractional seasonal variation of the hot water consumption about the reference.
        profile_data: Dataframe of the profile data.

    Returns:
        Series of consumption.
    """
    max_daily_consumption = ref_daily_consumption * (1.0+seasonal_variance)
    min_daily_consumption = ref_daily_consumption * (1.0-seasonal_variance)

    oframe = (
        pd.DataFrame(
            {'datetime': pd.to_datetime(datetimes)}
        )
        .assign(
            year = lambda df: df['datetime'].dt.year,
            doy = lambda df: df['datetime'].dt.day_of_year
        )
        # Shift up one, as the indices apply to the metered intervals which are ended by the current timeindex
        .assign(
            year = lambda df: df['year'].shift(1, fill_value = df['year'].iloc[0]),
            doy = lambda df: df['doy'].shift(1, fill_value = df['doy'].iloc[0])
        )
    )

    years = oframe['year'].unique()
    years = (
        pd.DataFrame({'year':years})
        .assign(
            max_doy = lambda df: df.apply(lambda rw: pd.to_datetime(f'{rw['year']}-01-14T00:00:00').day_of_year, axis=1),
            min_doy = lambda df: df.apply(lambda rw: pd.to_datetime(f'{rw['year']}-07-14T00:00:00').day_of_year, axis=1),
            doy_negrange = lambda df: df['min_doy'] - df['max_doy'],
            doy_posrange = lambda df: df['max_doy'] + df.apply(lambda rw: pd.to_datetime(f'{rw['year']}-12-31T00:00:00').day_of_year, axis=1) - df['min_doy']
        )
    )

    oframe = (
        oframe
        .set_index('year')
        .join(years.set_index('year'))
        .reset_index()
        .assign(
            demand_factor = lambda df: np.where(
                df['doy'] == df['max_doy'],
                1.0,
                np.where(
                    df['doy'] < df['max_doy'],
                    1.0 - (df['max_doy'] - df['doy']) / df['doy_posrange'],
                    np.where(
                        df['doy'] < df['min_doy'],
                        (df['min_doy'] - df['doy']) / df['doy_negrange'],
                        np.where(
                            df['doy'] == df['min_doy'],
                            0.0,
                            (df['doy'] - df['min_doy']) / df['doy_negrange'])
                    )
                )
            )
        )
        .assign(
            daily_consumption = lambda df: df['demand_factor'] * (max_daily_consumption-min_daily_consumption) + min_daily_consumption
        )
        .loc[:,['datetime','daily_consumption']]
        .assign(
            end_day_seconds = lambda df: (df['datetime'] - df['datetime'].dt.floor('D')).dt.total_seconds(),
            start_day_seconds = lambda df: df['end_day_seconds'].shift(1, fill_value = df['end_day_seconds'].iloc[0]),
            time_delta = lambda df: df['datetime'] - df['datetime'].shift(1, fill_value=df['datetime'].iloc[0])
        )
        .assign(
            end_day_seconds = lambda df: np.where(
                np.logical_and(df['start_day_seconds'] != df['end_day_seconds'],
                    df['end_day_seconds'] == 0),
                    3600 * 24,
                    df['end_day_seconds']
            )
        )
    )

    if oframe['time_delta'].iloc[1].total_seconds() == 86400:
        return (
            oframe
            .rename(columns={'daily_consumption': 'consumption'})
            .assign(consumption = lambda df: np.where(df['time_delta'].dt.total_seconds()==0, 0, df['consumption']))
            .loc[:,['datetime','consumption']]
        )

    oframe = oframe.set_index(['start_day_seconds', 'end_day_seconds'])

    time_spans = oframe.index.unique().to_frame()

    working_profiles = profiles_for_time_spans(time_spans, profile_data)

    oframe = oframe \
        .join(working_profiles) \
        .reset_index() \
        .assign(
            fraction_dhw_heat = lambda df: np.where(np.isnan(df['fraction_dhw_heat']), 0.0, df['fraction_dhw_heat']),
            consumption = lambda df: df['fraction_dhw_heat'] * df['daily_consumption']
        ) \
        .loc[:, ['datetime','consumption']]

    return oframe