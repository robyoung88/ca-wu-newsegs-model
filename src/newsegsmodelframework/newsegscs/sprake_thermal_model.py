"""The space heating demand model of the Sprake model: heating degree days, heat loss parameter and the daily profile.
"""
import os
import numpy as np
import pandas as pd
import numpy.typing as npt


from config import settings
from newsegsmodelframework import STATICDATA
lookup_dir = settings.get('SprakeDataLoc', STATICDATA / 'sprake_data')

CALIBRATION_DEGREE_DAYS = pd.read_excel(os.path.join(lookup_dir,
                                                     'calibration_heating_degree_days.xlsx'),
                                        sheet_name='heating_degree_days',
                                        header=0) \
    .assign(timestamp = lambda df: df['timestamp'].dt.tz_localize(tz='utc'))

TIMESERIES_DEGREE_DAYS = pd.read_excel(os.path.join(lookup_dir,
                                                    'heating_degree_days.xlsx'),
                                        sheet_name='heating_degree_days',
                                        header=0) \
    .assign(timestamp = lambda df: df['timestamp'].dt.tz_localize(tz='utc'))

# NB - these data are prospective i.e. timestamp marks start of hour of consumption
PROFILE_DATA = pd.read_excel(os.path.join(lookup_dir,
                                          r'space_heat_demand_profile_day.xlsx'),
                             sheet_name='space_heat_demand_profile_day',
                             header=0,
                             dtype={'timestamp':str})\
                .assign(timestamp = lambda df: pd.to_timedelta(df['timestamp']),
                        start_day_seconds = lambda df: df['timestamp'].dt.total_seconds(),
                        end_day_seconds = lambda df: df['start_day_seconds'].shift(-1, fill_value = df['start_day_seconds'].iloc[-1] + (df['start_day_seconds'].iloc[1] - df['start_day_seconds'].iloc[0])))

# REVIEW (unreferenced): no references to `calibrate_hlp` found in src/, scripts/ or data/.
def calibrate_hlp(target_specific_heat_loss: float = 52.0, #kWh/m²/yr
                  calibration_degree_days: npt.ArrayLike = np.asarray(CALIBRATION_DEGREE_DAYS['hdd_15_5'].values)
                  ) -> float:
    # degree days to degree hours
    """The heat loss parameter that gives a target annual specific heat loss.

    Args:
        target_specific_heat_loss: Specific heat loss (kWh/m^2/year) to calibrate to.
        calibration_degree_days: Degree days of the calibration year.

    Returns:
        The heat loss parameter.
    """
    dh = 24.0 * np.sum(calibration_degree_days)
    return target_specific_heat_loss / (dh / 1000.0)

HDD_BASE_TEMPERATURE = 15.5
"""Base temperature (degrees C) of the heating degree days."""

def heating_degree_days_from_temperature(
    datetimes: pd.DatetimeIndex,
    temperatures: npt.ArrayLike,
) -> pd.DataFrame:
    """Heating degree days (to 15.5 degrees C) of each day, from a series of air temperatures.

    The degree days of a day are the amount by which its mean temperature is below the base
    temperature, or zero. Each temperature is taken as the mean over the timestep ending at its
    datetime, as for the consumption of `get_spaceheat_energy_consumption`, so a temperature at
    midnight belongs to the day before.

    Args:
        datetimes: Datetimes at the end of the timestep of each temperature.
        temperatures: Air temperatures (degrees C).

    Returns:
        Dataframe of the `timestamp` (midnight) of each day and its degree days, `hdd_15_5`,
        in the format of `TIMESERIES_DEGREE_DAYS`.
    """
    srs = pd.Series(np.asarray(temperatures, dtype=np.float64), index = pd.DatetimeIndex(datetimes))
    days = (srs.index - pd.Timedelta(1, 'm')).floor('D')
    daily_mean = srs.groupby(days).mean()
    return pd.DataFrame({
        'timestamp': daily_mean.index,
        'hdd_15_5': np.clip(HDD_BASE_TEMPERATURE - daily_mean.to_numpy(), a_min = 0., a_max = None),
    })

def profiles_for_time_spans(time_spans, profile_data):
    """Fraction of the daily space heating demand in each of the time spans, from the profile.

    Args:
        time_spans: Dataframe of the start and end second of the day of each timestep.
        profile_data: Dataframe of the profile data.

    Returns:
        Dataframe of the fraction for each time span.
    """
    import sqlite3

    with sqlite3.connect(':memory:') as conn:
        profile_data.loc[:,['start_day_seconds','end_day_seconds','proportion_space_heating_demand']].to_sql('profile_data', conn, index = False)
        time_spans.to_sql('time_spans', conn, index = False)

        qry = '''
        select
            time_spans.start_day_seconds start_day_seconds,
            time_spans.end_day_seconds end_day_seconds,
            profile_data.start_day_seconds prof_sds,
            profile_data.end_day_seconds prof_eds,
            profile_data.proportion_space_heating_demand heat
        from
            time_spans join profile_data on
            not(time_spans.end_day_seconds <= profile_data.start_day_seconds) and not(time_spans.start_day_seconds >= profile_data.end_day_seconds)
        '''

        df = pd.read_sql_query(qry, conn)\
            .assign(
                window_length = lambda df: (np.minimum(df['end_day_seconds'], df['prof_eds']) - np.maximum(df['start_day_seconds'], df['prof_sds']))/3600.0,
                fraction_heat = lambda df: df['heat'] * df['window_length']
            ) \
            .groupby(['start_day_seconds', 'end_day_seconds']) \
            ['fraction_heat']\
            .sum()
        
    return df

def get_spaceheat_energy_consumption(datetimes,
                                     hlp:float, # W/m²/K
                                     gfa:float, # m²
                                     hdd:pd.DataFrame=TIMESERIES_DEGREE_DAYS,
                                     profile_data:pd.DataFrame=PROFILE_DATA
                                     ):
    """Energy consumption for space heating at each timestep.

    The demand of each day is the heating degree days (to 15.5 degrees C) times the floor area times the heat loss parameter (W/m^2/K), converted to kWh, and is distributed through the day by the profile. Raises `ValueError` if the datetimes are outside of the degree day data.

    Args:
        datetimes: Datetimes at the start of each timestep.
        hlp: Heat loss parameter.
        gfa: Gross floor area of a dwelling (m^2).
        hdd: Dataframe of heating degree days.
        profile_data: Dataframe of the profile data.

    Returns:
        Series of consumption.
    """
    oframe = (
        pd.DataFrame(
            {'datetime': pd.to_datetime(datetimes)}
        )
        .assign(
            shift_midnight = lambda df: df['datetime'] - pd.Timedelta(1, 'm'),
            date = lambda df: df['shift_midnight'].dt.floor("D")
        )
        .drop(
            columns = ['shift_midnight']
        )
    )

    start_day = oframe['date'].min()
    end_day = oframe['date'].max()
    
    if start_day < hdd['timestamp'].min() or end_day > hdd['timestamp'].max():
        raise ValueError('Requested datetimes are outside of degree day support; requested: ', start_day, ' to ', end_day, '; have ', hdd['timestamp'].min(), ' to ', hdd['timestamp'].max())
    
    working_hdd = (
        hdd
        .assign(date = lambda df: df['timestamp'].dt.floor("D"))
        .query('date >= @start_day & date <= @end_day')
        .assign(
            daily_consumption = lambda df: df['hdd_15_5'] * gfa * hlp * 24.0 / 1000.0
        )
    )

    oframe = (
        oframe
        .set_index('date')
        .join(working_hdd.loc[:,['date','daily_consumption']].set_index('date'))
        .reset_index()
        .assign(
            end_day_seconds = lambda df: (df['datetime'] - df['datetime'].dt.floor("D")).dt.total_seconds(),
            start_day_seconds = lambda df: df['end_day_seconds'].shift(1, fill_value = df['end_day_seconds'].iloc[0]),
            time_delta = lambda df: df['datetime'] - df['datetime'].shift(1, fill_value=df['datetime'].iloc[0])
        )
        .assign(
            end_day_seconds = lambda df: df['start_day_seconds'] + df['time_delta'].dt.total_seconds()
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
            fraction_heat = lambda df: np.where(np.isnan(df['fraction_heat']), 0.0, df['fraction_heat']),
            consumption = lambda df: df['fraction_heat'] * df['daily_consumption']
        ) \
        .loc[:, ['datetime','consumption']]

    return oframe