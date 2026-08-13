"""
Categorise energy timeseries by fractions of nominal capacity
"""
import numpy as np
import pandas as pd

from newsegsmodelframework.core import SECONDS_TO_HOURS

# Categorisation of wind production
WIND_PRODUCTION_CATEGORIES = pd.DataFrame(
    {
        'cf_min': [0.0, 0.05, 0.25, 0.5, 0.75, 0.95],
        'cf_max': [0.05, 0.25, 0.5, 0.75, 0.95, 9.99] # NB - high but finite final bin edge
    }
)
"""_summary_

Returns:
    _type_: _description_
"""

SOLAR_PRODUCTION_CATEGORIES = pd.DataFrame(
    {
        'frac_maxday_min': [0.0, 0.05, 0.25, 0.5, 0.75, 0.95],
        'frac_maxday_max': [0.05, 0.25, 0.5, 0.75, 0.95, 9.99] # NB - high but finite final bin edge
    }
)
"""_summary_
"""

def categorise_meter_by_capacity(
    meter_timeseries: pd.DataFrame|pd.Series,
    rated_capacity: float,
    meter_variable: str = 'wind_export',
    categories: pd.DataFrame = WIND_PRODUCTION_CATEGORIES,
) -> pd.DataFrame:
    """
    Augment production with categories based upon nameplate capacity.

    Args:
        meter_timeseries: A datetime-indexed dataframe
    """
    
    cat_labels = categories.apply(
        lambda rw: f"hrs_{rw['cf_min']*100:03.0f}_to_{rw['cf_max']*100:03.0f}",
        axis=1
    )

    # Divisions for the pd.cut function
    bins = np.concatenate([
        categories.loc[:,'cf_min'].values, 
        categories.loc[:,'cf_max'].values[-1:]
    ])

    working_df = (
        meter_timeseries
        .reset_index()
        .rename(columns={'index': 'datetime'})
        .assign(
            delta_hours = lambda df: (
                df['datetime'] \
                    - df['datetime'].shift(1, fill_value=df['datetime'].iloc[0])
            ).dt.seconds * SECONDS_TO_HOURS,
        )
        .query('delta_hours > 0')
        .assign(
            power = lambda df: (df[meter_variable] / df['delta_hours']),
            relative_utilisation = lambda df: df['power'] / rated_capacity,
            capacity_factor_range = lambda df: pd.cut(
                df['relative_utilisation'],
                bins=bins,
                include_lowest=True,
                right=False,
                labels=cat_labels
            )
        )
    )

    return working_df

def capacity_categorised_meter_summary(
    categorised_meter: pd.DataFrame,
    rated_capacity: float,
    categories: pd.DataFrame = WIND_PRODUCTION_CATEGORIES,
) -> pd.DataFrame:
    """
    Summary stats per production category.
    """
    # No need to do summaries by year, so we just run through a value count
    hrs_in_range = categorised_meter.groupby('capacity_factor_range', observed=False)['delta_hours'].sum()
    tot_hrs = hrs_in_range.sum()
    p_hrs_in_range = hrs_in_range / tot_hrs

    max_rel_production = categorised_meter.loc[:,'relative_utilisation'].max()
    max_power = max_rel_production * rated_capacity

    # Currently of the opinion that we just report back the full hours,
    # rather than normalise it to the length of a year.
    odf = (
        pd.DataFrame(p_hrs_in_range)
        .rename(columns={'delta_hours': 'horizon_fraction'})
        .assign(
            hours = hrs_in_range,
            min_power = categories.loc[:, 'cf_min'].values * rated_capacity,
            max_power = categories.loc[:, 'cf_max'].values * rated_capacity,
        )
    )
    odf.loc[odf.index[-1], 'max_power'] = max_power

    return odf

def capacity_categorised_meter_summary_to_interface(
        ccps: pd.DataFrame
) -> dict:
    """
    Converts the summary dataframe into the format expected by the interface
    """
    return ccps.to_dict(orient='index')

def categorise_meter_by_max_record(
    meter_timeseries: pd.DataFrame|pd.Series,
    max_record: float,
    meter_variable: str,
    categories: pd.DataFrame = SOLAR_PRODUCTION_CATEGORIES
) -> pd.DataFrame:
    """
    Augment meter data with categories based upon maximum production

    Args:
        meter_timeseries: A datetime-indexed series or dataframe
    """

    cat_labels = categories.apply(
        lambda rw: f"days_{rw['frac_maxday_min']*100:03.0f}_to_{rw['frac_maxday_max']*100:03.0f}",
        axis=1
    )

    # Divisions for the pd.cut function
    bins = np.concatenate([
        categories.loc[:,'frac_maxday_min'].values, 
        categories.loc[:,'frac_maxday_max'].values[-1:]
    ])

    working_df = (
        meter_timeseries
        .reset_index()
        .assign(
            relative_value = lambda df: df[meter_variable] / max_record,
            value_category = lambda df: \
                pd.cut(
                    df['relative_value'],
                    bins=bins,
                    include_lowest=True,
                    right=False,
                    labels=cat_labels
                )
        )
    )

    return working_df

def max_record_categorised_meter_summary(
    categorised_meter: pd.DataFrame,
    max_record: float,
    categories: pd.DataFrame = SOLAR_PRODUCTION_CATEGORIES,
) -> pd.DataFrame:
    """
    Summary stats per value category
    """
    days_in_range = categorised_meter.groupby('value_category', observed=False)['day_index'].count()
    tot_days = days_in_range.sum()
    p_days_in_range = days_in_range / tot_days

    max_relative_value = categorised_meter['relative_value'].max() # Most cases, will be 1
    max_value = max_record * max_relative_value

    odf = (
        pd.DataFrame(p_days_in_range)
        .rename(columns={'day_index': 'horizon_fraction'})
        .assign(
            days = days_in_range,
            min_value = categories['frac_maxday_min'].values * max_record,
            max_value = categories['frac_maxday_max'].values * max_record
        )
    )
    odf.loc[odf.index[-1], 'max_value'] = max_value

    return odf

def max_record_categorised_meter_summary_to_interface(
        mrcps: pd.DataFrame
) -> dict:
    """
    Converts the summary dataframe into the format expected by the interface
    """
    return mrcps.to_dict(orient='index')
