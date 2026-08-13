"""
Summary stats for generation or consumption.

Provides the following stats, broken down by meter type:
- Total metered energy
- Mean annual energy (by complete years from start)
- Minimum annual energy (by complete years from start)
- Maximum annual energy (by complete years from start)
"""
import pandas as pd

from newsegsmodelframework.newsegsstats.core import assign_year_index, assign_day_index

def meter_annual_summary(
    data: pd.DataFrame | pd.Series,
    agg_operations: list = ['sum','mean','min','max'],
) -> pd.DataFrame:
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
        data = data.pipe(assign_year_index).query('year_index >= 0')

    ann_smry = (
        data
        .groupby('year_index')
        .agg('sum')
        .agg(agg_operations) 
    )

    return ann_smry

def meter_annual_summary2(
    data: pd.DataFrame|pd.Series,
    agg_operations = ['sum','mean','min','max']
) -> pd.DataFrame:
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
        data = data.pipe(assign_year_index).query('year_index >= 0')

    return (
        data
        .groupby('year_index')
        .agg('sum')
        .agg(agg_operations)
        .melt(ignore_index=False)
        .reset_index()
        .rename(columns={'index': 'statistic'})
        .loc[:, ['variable', 'statistic', 'value']]
    )

def meter_annual_summary_to_interface(
        meter_annual_summary: pd.DataFrame
    ) -> dict:
    """
    Converts the summary dataframe into the format expected by the interface
    """
    return meter_annual_summary.to_dict()

def meter_annual_summary2_to_interface(
        meter_annual_summary: pd.DataFrame
    ) -> dict:
    """
    Converts the summary dataframe into the format expected by the interface
    """
    return meter_annual_summary.to_dict(orient='list')

def meter_perday_summary(data: pd.DataFrame|pd.Series) -> pd.DataFrame:
    """
    Summary stats for generation or consumption meters per-day
    """

    if isinstance(data, pd.Series):
        data = data.to_frame()

    if not 'day_index' in data.columns:
        data = data.pipe(assign_day_index, shift=0).query('day_index >= 0')
    
    smry = (
        data
        .groupby('day_index')
        .agg('sum')
        .agg(
            ['sum', 'mean', 'min', 'max']
        ) 
    )

    return smry
