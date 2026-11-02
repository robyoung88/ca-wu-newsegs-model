"""Helper functions for NewsegsFinance."""
import pandas as pd

from newsegsmodelframework.core.timespan import year_index

def discount_factor_discrete(
        datetimes:pd.Series, 
        discount_rate:float
    ) -> pd.Series:
    """Return series of (left-aligned) discount factors for times in series.

    Args:
        datetimes: Series of datetimes.
        discount_rate: Discount rate as a float.

    Returns:
        Series of discount factors indexed by the input datetimes.

    Notes:
        Discount factors are applied in discrete years (per https://pmc.ncbi.nlm.nih.gov/articles/PMC4661216/#Sec9).
        A year is determined to have passed if the numeric year has increased and the day of year is >= the first
        day of the series. This implies that the calendar date of increment may vary depending on whether the present
        year is a leap year.
    """
    idx = year_index(datetimes)

    return pd.Series(data = (1.0 + discount_rate)**(-idx), index=datetimes)

def apply_discount_factor(
    undiscounted_df: pd.DataFrame, 
    discount_rate:float, 
    shift:int=0
) -> pd.DataFrame:
    """Apply a discrete discount factor to a date-indexed DataFrame.

    Args:
        undiscounted_df: DataFrame indexed by date, containing values to discount.
        discount_rate: Discount rate as a float.
        shift: Number of periods to shift the discount factors by.

    Returns:
        DataFrame with values discounted by the computed discount factors.
    """
    if len(undiscounted_df) == 0:
        return undiscounted_df 
        
    disc_factor = discount_factor_discrete(pd.Series(undiscounted_df.index), discount_rate)
    if shift != 0:
        disc_factor = disc_factor.shift(shift, fill_value=1.0) # Assuming shift will be +1 to account for end-of-interval accrued costs
    return undiscounted_df.apply(lambda col: col*disc_factor, axis=0)

def sum_all_to_horizon(
    date_indexed_df: pd.DataFrame, 
    horizon: pd.Timestamp | pd.Timedelta | None = None
) -> float:
    """Return the sum of all values up to a horizon.

    Args:
        date_indexed_df: DataFrame indexed by date containing values to sum.
        horizon: Optional horizon as a Timestamp or Timedelta. If None, the last
            date in the index is used.

    Returns:
        The sum of all values in the DataFrame up to and including the horizon.
    """
    if horizon is None:
        horizon = date_indexed_df.index[-1]
    elif isinstance(horizon, pd.Timedelta):
        horizon = date_indexed_df.index[0] + horizon
    date_indexed_df = date_indexed_df.loc[date_indexed_df.index<=horizon, :]
    return date_indexed_df.sum().sum()
