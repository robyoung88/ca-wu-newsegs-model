# Helper functions for aligning timeseries with elexon profile data

import os
import datetime
import numpy as np
import pandas as pd

import holidays

from config import settings
# Where to find elexon profile data
lookup_dir = settings.get('SprakeDataLoc')

# These data are retrospective, i.e. timestamp marks end of half-hour of demand
PROFILE_DATA = pd.read_excel(os.path.join(lookup_dir, 
                                          r"Average_Profiling_data_201314_evaluated@10yearNET_v1.0.xlsx"),
                            sheet_name="Average Profile Class data",
                            header=2, nrows=48, # For Profile 1
                            dtype={'Settlement period':str}
                            ) \
                .assign(
                    **{'Settlement period': lambda df: pd.to_timedelta(df['Settlement period']),
                       'end_day_seconds': lambda df: df['Settlement period'].dt.total_seconds()}
                ) \
                .assign(
                    # Because these periods are retrospective, we end at midnight and a 0. Convert it to a 24
                    end_day_seconds = lambda df: np.where(df['end_day_seconds']==0.0, 24.0*3600.0, df['end_day_seconds']),
                    start_day_seconds = lambda df: df['end_day_seconds'].shift(1, fill_value = 0.0)
                ) \
                .melt(id_vars=['Settlement period','start_day_seconds','end_day_seconds'],
                      var_name="profile",value_name="consumption_rate") \
                .assign(
                    split_prof = lambda df: df['profile'].str.split(" "),
                    elexon_season = lambda df: df.apply(lambda rw: rw['split_prof'][0].lower(), axis=1),
                    elexon_day = lambda df: df.apply(lambda rw: rw['split_prof'][1].lower(), axis=1),
                ) \
                .loc[:, ['start_day_seconds', 'end_day_seconds', 'elexon_season', 'elexon_day', 'consumption_rate']]

# First elexon season change in year is spring - first day of year of BST
# This is last Sunday in March
def get_first_day_bst(year:int) -> pd.Timestamp:
    """
    Return the date of the first day of the year when clocks go forward
    """
    # Step 1: get day of last date in March
    last_day = pd.Timestamp(f"{year}-03-31", tz='utc')
    dow = last_day.day_of_week
    # Step 2: back up to nearest Sunday (day_of_week == 6, Monday = 0)
    if (dow == 6):
        return last_day
    else:
        return last_day - pd.Timedelta(days=dow+1)

def get_start_elexon_spr(year:int) -> pd.Timestamp:
    """
    Start of elexon spring profile - first day BST
    """
    return get_first_day_bst(year)

# Second elexon season change in year is summer, defined in terms of August
# or "Late Summer" bank holiday. This is last Monday in August
def get_august_bank_holiday(year) -> pd.Timestamp:
    # Step 1: get day of last date in August
    last_day = pd.Timestamp(f"{year}-08-31", tz='utc')
    dow = last_day.day_of_week
    # Step 2: back up to nearest Monday (day_of_week == 0, Monday = 0)
    if (dow == 0):
        return last_day
    else:
        return last_day - pd.Timedelta(days=dow)

def get_start_elexon_smr(year:int) -> pd.Timestamp:
    """
    Start of elexon summer profile - sixteenth Saturday preceding August BH
    """
    abh = get_august_bank_holiday(year)
    return abh - pd.Timedelta(days = 2 + 15 * 7)

def get_start_elexon_hsr(year:int) -> pd.Timestamp:
    """
    Start of elexon high summer profile - sixth Saturday preceding August BH
    """
    abh = get_august_bank_holiday(year)
    return abh - pd.Timedelta(days = 2 + 5 * 7)

def get_start_elexon_aut(year:int) -> pd.Timestamp:
    """
    Start of elexon autumn profile - Monday following August BH
    """
    abh = get_august_bank_holiday(year)
    return abh + pd.Timedelta(days = 7)

def get_first_day_gmt(year:int) -> pd.Timestamp:
    """
    Return the date of the first day of the year when clocks go back

    This is the last Sunday in October
    """
    # Step 1: get day of last date in October
    last_day = pd.Timestamp(f"{year}-10-31", tz='utc')
    dow = last_day.day_of_week
    # Step 2: back up to nearest Sunday (day_of_week == 6, Monday = 0)
    if (dow == 6):
        return last_day
    else:
        return last_day - pd.Timedelta(days=dow+1)

def get_start_elexon_wtr(year:int) -> pd.Timestamp:
    """
    Start of elexon winter profile - First day of return to GMT
    """
    return get_first_day_gmt(year)

def characterise_dates_elexon(datetimes,
                              hols = holidays.country_holidays('GB', subdiv='WLS')):
    """
    Categorise datetimes by season and day of week per elexon profiling schedule

    Holidays are assigned Sunday profiles if they fall on a weekday.
    """
    oframe = (
        pd.DataFrame(
            {'datetime': pd.to_datetime(datetimes)})
        .assign(
            day_no = lambda df: df['datetime'].dt.day_of_week,
            year = lambda df: df['datetime'].dt.year
        )
    )

    years = oframe['year'].unique()
    index_dates = (
        pd.DataFrame({'year':years})
        .assign(
            first_day_spr = lambda df: df.apply(lambda rw: get_start_elexon_spr(rw['year']), axis=1),
            first_day_smr = lambda df: df.apply(lambda rw: get_start_elexon_smr(rw['year']), axis=1),
            first_day_hsr = lambda df: df.apply(lambda rw: get_start_elexon_hsr(rw['year']), axis=1),
            first_day_aut = lambda df: df.apply(lambda rw: get_start_elexon_aut(rw['year']), axis=1),
            first_day_wtr = lambda df: df.apply(lambda rw: get_start_elexon_wtr(rw['year']), axis=1)
        )
    )

    oframe = (
        oframe
        .set_index('year')
        .join(index_dates.set_index('year'))
        .reset_index()
        .assign(
            is_holiday = lambda df: df.apply(lambda rw: rw['datetime'] in hols, axis=1),
            is_weekday = lambda df: df['day_no'] < 5,
            is_sat = lambda df: df['day_no'] == 5,
            is_sun = lambda df: df['day_no'] == 6,
            elexon_season = lambda df: np.where(
                df['datetime'] >= df['first_day_wtr'], 'wtr',
                np.where(
                    df['datetime'] >= df['first_day_aut'], 'aut',
                    np.where(
                        df['datetime'] >= df['first_day_hsr'], 'hsr',
                        np.where(
                            df['datetime'] >= df['first_day_smr'], 'smr',
                            np.where(
                                df['datetime'] >= df['first_day_spr'], 'spr',
                                'wtr'
                            )
                        )
                    )
                )
            ),
            elexon_day = lambda df: np.where(
                df['is_sat'], 'sat',
                np.where(
                    df['is_sun'], 'sun',
                    np.where(
                        df['is_holiday'], 'sun',
                        'wd'
                    )
                )
            )
        )
    )

    if (os.environ['ENV_FOR_DYNACONF'] == 'spraketest'):
        # Original Sprake model does not consider holidays
        oframe = oframe \
            .assign(
                elexon_day = lambda df: np.where(
                    df['is_weekday'],
                    'wd',
                    df['elexon_day']

                )
            )

    return oframe.loc[:,['datetime','elexon_season','elexon_day']]

def elexon_profiles_for_time_spans(time_spans, profile_data):
    """
    Convert elexon profile data to the averaging periods used in the model time series
    """
    import sqlite3

    with sqlite3.connect(':memory:') as conn:
        profile_data.loc[:,['start_day_seconds','end_day_seconds',
                            'elexon_season','elexon_day',
                            'consumption_rate']].to_sql('profile_data', conn, index = False)
        time_spans.to_sql('time_spans', conn, index = False)

        qry = '''
        select
            time_spans.start_day_seconds start_day_seconds,
            time_spans.end_day_seconds end_day_seconds,
            profile_data.start_day_seconds prof_sds,
            profile_data.end_day_seconds prof_eds,
            profile_data.elexon_season elexon_season,
            profile_data.elexon_day elexon_day,
            profile_data.consumption_rate consumption_rate
        from
            time_spans join profile_data on
            not(time_spans.end_day_seconds <= profile_data.start_day_seconds) and not(time_spans.start_day_seconds >= profile_data.end_day_seconds)
        '''

        df = pd.read_sql_query(qry, conn)\
            .assign(
                window_length = lambda df: (np.minimum(df['end_day_seconds'], df['prof_eds']) - np.maximum(df['start_day_seconds'], df['prof_sds']))/3600.0,
                consumption = lambda df: df['consumption_rate'] * df['window_length']
            ) \
            .groupby(['start_day_seconds', 'end_day_seconds','elexon_season','elexon_day']) \
            ['consumption']\
            .sum()
        
    return df

def get_elexon_consumption(datetimes,
                           profile_data = PROFILE_DATA):
    """
    Given a regular timeseries, get the elexon profile consumption between adjacent entries

    If spanning multiple days, midnight times must be present in the series
    """
    datetimes = pd.to_datetime(datetimes)
    if len(datetimes) < 2:
        raise ValueError("Consumption is between adjacent times, require at least 2")

    # Our datetimes are retrospective (i.e. are at the end of the interval).
    # In order to make sure they are assigned the correct elexon period (at midnight), we need to get the start
    # of the interval
    start_datetimes = pd.Series(datetimes).shift(1, fill_value=datetimes[0])
    oframe = characterise_dates_elexon(start_datetimes) \
        .rename(columns={'datetime':'start_datetime'}) \
        .assign(
            datetime = datetimes,
            end_day_seconds = lambda df: (df['datetime'] - df['datetime'].dt.floor('D')).dt.total_seconds(),
            start_day_seconds = lambda df: df['end_day_seconds'].shift(1, fill_value = df['end_day_seconds'].iloc[0]),
            time_delta = lambda df: df['datetime'] - df['datetime'].shift(1, fill_value=df['datetime'].iloc[0])
        ) \
        .assign(
            end_day_seconds = lambda df: df['start_day_seconds'] + df['time_delta'].dt.total_seconds()
        )

    oframe = oframe.set_index(['start_day_seconds', 'end_day_seconds'])

    time_spans = oframe.index.unique().to_frame()

    working_profiles = elexon_profiles_for_time_spans(time_spans, profile_data)

    oframe = oframe\
        .reset_index()\
        .set_index(['start_day_seconds','end_day_seconds','elexon_season','elexon_day']) \
        .join(working_profiles) \
        .reset_index() \
        .assign(
            consumption = lambda df: np.where(np.isnan(df['consumption']), 0.0, df['consumption'])
        )

    return oframe
