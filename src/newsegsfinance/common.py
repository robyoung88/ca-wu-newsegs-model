import numpy as np
import pandas as pd

def discount_factor_discrete(datetimes:pd.Series, discount_rate:float) -> pd.Series:
    """
    Return series of (left-aligned) discount factors for times in series

    Discount factors are applied in discrete years (per https://pmc.ncbi.nlm.nih.gov/articles/PMC4661216/#Sec9)
    A year is determined to have passed if the numeric year has increased and the day of year is >= the first
    day of the series. This implies that the calendar date of increment may vary depending on whether the present
    year is a leap year
    """
    yearday = datetimes.dt.day_of_year
    year = datetimes.dt.year
    startday = yearday.iloc[0]
    startyear = year.iloc[0]
    idx = ((year - startyear - 1) + 1 *((yearday - startday) >=0)).to_numpy()

    return pd.Series(data = (1.0 + discount_rate)**(-idx), index=datetimes)

def apply_discount_factor(undiscounted_df:pd.DataFrame, discount_rate:float, shift:int=0):
    if len(undiscounted_df) == 0:
        return undiscounted_df 
        
    disc_factor = discount_factor_discrete(pd.Series(undiscounted_df.index), discount_rate)
    if shift != 0:
        disc_factor = disc_factor.shift(shift, fill_value=1.0) # Assuming shift will be +1 to account for end-of-interval accrued costs
    return undiscounted_df.apply(lambda col: col*disc_factor, axis=0)

def sum_all_to_horizon(date_indexed_df:pd.DataFrame, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
    if horizon is None:
        horizon = date_indexed_df.index[-1]
    elif isinstance(horizon, pd.Timedelta):
        horizon = date_indexed_df.index[0] + horizon
    date_indexed_df = date_indexed_df.loc[date_indexed_df.index<=horizon, :]
    return date_indexed_df.sum().sum()