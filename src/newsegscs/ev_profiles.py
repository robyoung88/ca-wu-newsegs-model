# Helper functions for aligning timeseries with EV charging profile data

import os
import numpy as np
import pandas as pd

import holidays

from config import settings
lookup_dir = settings.get('SprakeDataLoc')

# Profile data is the proportion of annual residential consumption for EV per period
# in periods of one hour through 2017
# https://smarter.energynetworks.org/projects/nia_ngso0021
# Notably, 2017 is not a leap year.
# Regardless, to make these data representative of weekly as well as yearly trend, they need characterisation
PROFILE_DATA = pd.read_excel(os.path.join(lookup_dir,
                                          r'NG EV Charging Behaviour Study - Demand Profiles - V3 - External (11-04-2019 00-00-00).xlsx'),
                                          sheet_name='GB Level Profile',
                                          header = 22,
                                          usecols=[0,2])\
                            .rename(columns={'Timestamp':'datetime'})

def characterise_dates_evprofile(datetimes,
                                 hols:holidays.HolidayBase = holidays.country_holidays('GB', subdiv='WLS')):
    """
    Assign variables to characterise a datetime series or DataFrame be ev charging averaging periods
    """
    if isinstance(datetimes, pd.DataFrame):
        if not 'datetime' in datetimes.columns:
            raise ValueError('Passed DataFrame must contain `datetime` column')
        oframe = datetimes
    else:
        oframe = pd.DataFrame({'datetime': pd.to_datetime(datetimes)})
    
    # As we are going month by month, we will not use bank holidays as their own category
    # as the data are too sparse - will just roll them into the Sunday profile.
    oframe = (
        oframe
        .assign(
            month_n = lambda df: df['datetime'].dt.month,
            day_n = lambda df: df['datetime'].dt.day_of_week,
            period_hour = lambda df: df['datetime'].dt.hour,
            is_holiday = lambda df: df.apply(lambda rw: rw['datetime'] in hols, axis=1),
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
def characterise_profile_data(profile_data:pd.DataFrame,
                              hols:holidays.HolidayBase = holidays.country_holidays('GB', subdiv='ENG')):
    
    return (
        profile_data.pipe(characterise_dates_evprofile, hols)
        .groupby(['month_n','prof_day','period_hour'])
        ['Residential']
        .mean()
    )

PROFILE_DATA_CHARACTERISED = characterise_profile_data(PROFILE_DATA).to_frame().reset_index()

def ev_profiles_for_time_spans(time_spans,
                               profile_data_characterised=PROFILE_DATA_CHARACTERISED):
    time_spans = time_spans.to_frame()
    normalised_profiles_characterised = profile_data_characterised
    # Where a span ends at midnight but is not zero-length, set end to 24 
    # to allow less-than logic to work on filtering
    time_spans = time_spans \
        .assign(
            shifted_end = lambda df: np.logical_and(
                df['start_hour'] != df['end_hour'],
                df['end_hour'] == 0),
            end_hour = lambda df: np.where(df['shifted_end'], 24, df['end_hour'])
            )

    averaged_profiles = []
    for _, rw in time_spans.iterrows():
        profdata = (
            normalised_profiles_characterised
            .query('month_n == @rw["month_n"] & prof_day == @rw["prof_day"]')
            .query('period_hour >= @rw["start_hour"] & period_hour < @rw["end_hour"]')
            ['Residential']
            .mean()
        )
        
        averaged_profiles.append(
            pd.DataFrame(rw.to_dict(),index=[0]).assign(consumption_rate = profdata)
        )

    retprof = pd.concat(averaged_profiles)

    retprof = retprof \
        .assign(end_hour = lambda df: np.where(
            df['shifted_end'],
            0,
            df['end_hour']
        )) \
        .drop(columns=['shifted_end']) \
        .fillna(0.0)
    
    return retprof

# TODO: this is too slow
def get_ev_consumption(datetimes,
                       annual_consumption:float = 2000.0,
                       normalised_profiles_characterised=PROFILE_DATA_CHARACTERISED,
                       hols:holidays.HolidayBase = holidays.country_holidays('GB', subdiv='WLS')):
    """
    Given a regular timeseries, get the profiled EV consumption between adjacent entries

    If spanning multiple days, midnight times must be present in the series
    """

    datetimes = pd.to_datetime(datetimes)
    if len(datetimes) < 2:
        raise ValueError("Consumption is between adjacent times, require at least 2")
    
    oframe = (
        characterise_dates_evprofile(datetimes, hols)
        .assign(end_hour = lambda df: df['period_hour'],
                start_hour = lambda df: df['end_hour'].shift(1, fill_value = df['end_hour'].iloc[0]))
    )

    time_spans = oframe.set_index(['month_n','prof_day','start_hour','end_hour']).index.unique()

    working_profiles = ev_profiles_for_time_spans(time_spans,normalised_profiles_characterised)

    oframe = oframe \
        .set_index(['month_n','prof_day','start_hour','end_hour']) \
        .join(working_profiles.set_index(['month_n','prof_day','start_hour','end_hour'])) \
        .reset_index() \
        .assign(
            delta_hrs = lambda df: (df['datetime'] - df['datetime'].shift(1, fill_value = df['datetime'].iloc[0])).dt.total_seconds() / 3600.0,
            consumption = lambda df: df['consumption_rate'] * df['delta_hrs'] * annual_consumption
        )
    
    return oframe