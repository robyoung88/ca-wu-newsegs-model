"""
Summary stats for generation or consumption.

Provides the following stats, broken down by meter type:
- Total metered energy
- Mean annual energy (by complete years from start)
- Minimum annual energy (by complete years from start)
- Maximum annual energy (by complete years from start)
"""
import pandas as pd

from src.stats.core import assign_year_index

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
        data = data.pipe(assign_year_index)
    
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
