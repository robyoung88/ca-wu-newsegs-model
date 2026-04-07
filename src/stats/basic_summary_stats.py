"""
Summary stats for generation or consumption.

Provides the following stats, broken down by meter type:
- Total metered energy
- Mean annual energy (by complete years from start)
- Minimum annual energy (by complete years from start)
- Maximum annual energy (by complete years from start)
"""
import pandas as pd

from src.core.timespan import year_index

def apply_year_index(
        data: pd.DataFrame|pd.Series,
        shift: int = 1,
) -> pd.DataFrame:
    """
    Augment a datetime-indexed meter dataframe with the year index.

    The year index will be shifted by default so that the zeroth time node
    is set to year 0, assuming that meters are retrospective (i.e. sum
    over previous timestep)
    """
    if isinstance(data, pd.Series):
        data = data.to_frame()

    if "year_index" in data.columns:
        raise UserWarning('year_index is already present in data')
    ann_data = data.assign(year_index = lambda df: year_index(pd.Series(df.index)))

    if shift > 0:
        ann_data = ann_data.assign(year_index = lambda df: df['year_index'].shift(shift, fill_value=0))
    elif shift <0:
        ann_data = ann_data.assign(year_index = lambda df: df['year_index'].shift(shift, fill_value=df['year_index'].iloc[-1]))
    
    return ann_data

def meter_annual_summary(data: pd.DataFrame|pd.Series) -> pd.DataFrame:
    """
    Summary stats for generation or consumption meters.

    Args:
        data: 
            A datetime-indexed dataframe consisting only of meter data.
            If a year_index column is present, it will be used,
            else it shall be generated and used.

    Returns:

    """
    if isinstance(data, pd.Series):
        data = data.to_frame()
    
    if not 'year_index' in data.columns:
        data = data.pipe(apply_year_index)
    
    ann_smry = (
        data
        .groupby('year_index')
        .agg('sum')
        .agg(
            ['sum', 'mean', 'min', 'max']
        )
    )

    return ann_smry

def meter_annual_summary_to_interface(
        meter_annual_summary: pd.DataFrame
    ) -> dict:
    """
    Converts the summary dataframe into the format expected by the interface
    """
    return meter_annual_summary.to_dict()
