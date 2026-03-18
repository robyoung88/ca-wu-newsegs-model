import os
import numpy as np
import pandas as pd
import numpy.typing as npt

from config import settings
lookup_dir = settings.get('SprakeDataLoc')

CALIBRATION_DEGREE_DAYS = pd.read_excel(os.path.join(lookup_dir,
                                                     'calibration_heating_degree_days.xlsx'),
                                        sheet_name='heating_degree_days',
                                        header=0)

TIMESERIES_DEGREE_DAYS = pd.read_excel(os.path.join(lookup_dir,
                                                    'heating_degree_days.xlsx'),
                                        sheet_name='heating_degree_days',
                                        header=0)

# NB - these data are prospective i.e. timestamp marks start of hour of consumption
PROFILE_DATA = pd.read_excel(os.path.join(lookup_dir,
                                          r'space_heat_demand_profile_day.xlsx'),
                             sheet_name='space_heat_demand_profile_day',
                             header=0,
                             dtype={'timestamp':str})\
                .assign(timestamp = lambda df: pd.to_timedelta(df['timestamp']),
                        start_day_seconds = lambda df: df['timestamp'].dt.total_seconds(),
                        end_day_seconds = lambda df: df['start_day_seconds'].shift(-1, fill_value = df['start_day_seconds'].iloc[-1] + (df['start_day_seconds'].iloc[1] - df['start_day_seconds'].iloc[0])))

def calibrate_hlp(target_specific_heat_loss:float=52.0, #kWh/m²/yr
                  calibration_degree_days:npt.ArrayLike=CALIBRATION_DEGREE_DAYS['hdd_15_5'].values
                  ) -> float:
    # degree days to degree hours
    dh = 24.0 * np.sum(calibration_degree_days)
    return target_specific_heat_loss / (dh / 1000.0)

def profiles_for_time_spans(time_spans, profile_data):
    import sqlite3

    with sqlite3.connect(':memory:') as conn:
        PROFILE_DATA.loc[:,['start_day_seconds','end_day_seconds','proportion_space_heating_demand']].to_sql('profile_data', conn, index = False)
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
    oframe = (
        pd.DataFrame(
            {'datetime': pd.to_datetime(datetimes)}
        )
        .assign(
            date = lambda df: df['datetime'].dt.floor("D")
        )
    )

    start_day = oframe['date'].min()
    end_day = oframe['date'].max()
    
    if start_day < hdd['timestamp'].min() or end_day > hdd['timestamp'].max():
        raise ValueError('Requested datetimes are outside of degree day support')
    
    working_hdd = (
        hdd
        .assign(date = lambda df: df['timestamp'].dt.floor("D"))
        .query('date >= @start_day & date <= @end_day')
        .assign(
            daily_consumption = lambda df: df['hdd_15_5'] * gfa * hlp * 24.0
        )
    )

    oframe = (
        oframe
        .set_index('date')
        .join(working_hdd.loc[:,['date','daily_consumption']].set_index('date'))
        .reset_index()
        .assign(
            end_day_seconds = lambda df: (df['datetime'] - df['date']).dt.total_seconds(),
            start_day_seconds = lambda df: df['end_day_seconds'].shift(1, fill_value = df['end_day_seconds'].iloc[0]),
            time_delta = lambda df: df['datetime'] - df['datetime'].shift(1, fill_value=df['datetime'].iloc[0])
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
            consumption = lambda df: df['fraction_heat'] * df['daily_consumption']
        ) \
        .loc[:, ['datetime','consumption']]

    return oframe