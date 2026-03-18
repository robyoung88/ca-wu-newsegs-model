# Helper functions for aligning timeseries with elexon profile data

import os
import datetime
import numpy as np
import pandas as pd

import holidays

from config import settings
# Where to find elexon profile data
lookup_dir = settings.get('SprakeDataLoc')

PROFILE_DATA = pd.read_excel(os.path.join(lookup_dir, 
                                          r"Average_Profiling_data_201314_evaluated@10yearNET_v1.0.xlsx"),
                            sheet_name="Average Profile Class data",
                            header=2,nrows=48 # For Profile 1
                            ) \
                .melt(id_vars='Settlement period',var_name="profile",value_name="consumption_rate") \
                .assign(
                    split_prof = lambda df: df['profile'].str.split(" "),
                    elexon_season = lambda df: df.apply(lambda rw: rw['split_prof'][0].lower(), axis=1),
                    elexon_day = lambda df: df.apply(lambda rw: rw['split_prof'][1].lower(), axis=1),
                    settlement_end = lambda df: df['Settlement period'],
                    settlement_start = lambda df: df['settlement_end'].shift(1, fill_value = datetime.time(0))
                ) \
                .loc[:, ['settlement_start', 'settlement_end', 'elexon_season', 'elexon_day', 'consumption_rate']]

# First elexon season change in year is spring - first day of year of BST
# This is last Sunday in March
def get_first_day_bst(year:int) -> pd.Timestamp:
    """
    Return the date of the first day of the year when clocks go forward
    """
    # Step 1: get day of last date in March
    last_day = pd.Timestamp(f"{year}-03-31")
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
    last_day = pd.Timestamp(f"{year}-08-31")
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
    last_day = pd.Timestamp(f"{year}-10-31")
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

    return oframe.loc[:,['datetime','elexon_season','elexon_day']]

def elexon_profiles_for_time_spans(profile_data, time_spans):
    """
    Convert elexon profile data to the averaging periods used in the model time series
    """
    time_spans = time_spans.to_frame()
    # Where time_span ends at midnight, will need to set to 23:59:59 to ensure spans increase
    # over day
    # but ignore zero-length spans for timeseries start
    time_spans = time_spans \
        .assign(shifted_end = lambda df: np.logical_and(df['start_time'] != df['end_time'],
                           df['end_time'] == datetime.time(0)),
                end_time = lambda df: np.where(
                    df['shifted_end'],
                    datetime.time(23,59,59),
                    df['end_time']
                ))

    averaged_profiles = []
    for _, rw in time_spans.iterrows():
        # Perform simple mean, assuming that we're going to be aligned to the settlement periods
        profdata = profile_data.query('((@rw["start_time"] >= settlement_start) & (@rw["start_time"] < settlement_end)) or ((@rw["end_time"] > settlement_start) & (@rw["end_time"] <= settlement_end))')
        consump = profdata.groupby(['elexon_season', 'elexon_day'])['consumption_rate'].mean().to_frame().reset_index()
        #avprof = pd.concat([consump, rw.reset_index(drop=True)], axis=1)
        avprof = consump.assign(
            start_time = rw['start_time'],
            end_time = rw['end_time'],
            shifted_end = rw['shifted_end']
        )
        averaged_profiles.append(avprof)
    
    retprof = pd.concat(averaged_profiles)

    retprof = retprof \
        .assign(end_time = lambda df: np.where(
            df['shifted_end'],
            datetime.time(0),
            df['end_time']
        )) \
        .drop(columns=['shifted_end'])

    return retprof 

def get_elexon_consumption(datetimes,
                           profile_data = PROFILE_DATA):
    """
    Given a regular timeseries, get the elexon profile consumption between adjacent entries

    If spanning multiple days, midnight times must be present in the series
    """
    datetimes = pd.to_datetime(datetimes)
    if len(datetimes) < 2:
        raise ValueError("Consumption is between adjacent times, require at least 2")

    # Do we check and enforce regularity, or do we just assume that it's occurred?
    oframe = characterise_dates_elexon(datetimes) \
        .assign(
            end_time = lambda df: df['datetime'].dt.time,
            start_time = lambda df: df['end_time'].shift(1, fill_value = df['end_time'].iloc[0])
        )

    time_spans = oframe.set_index(['start_time','end_time']).index.unique()

    working_profiles = elexon_profiles_for_time_spans(profile_data, time_spans)

    oframe = oframe\
        .set_index(['elexon_season','elexon_day','start_time','end_time']) \
        .join(working_profiles.set_index(['elexon_season','elexon_day','start_time','end_time'])) \
        .reset_index() \
        .assign(
            delta_hrs = lambda df: (df['datetime'] - df['datetime'].shift(1, fill_value = df['datetime'].iloc[0])).dt.total_seconds() / 3600.0,
            consumption = lambda df: df['consumption_rate'] * df['delta_hrs']
        )

    return oframe
