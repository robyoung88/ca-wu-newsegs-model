"""
Locate and return the occurrence of maximum and minimum values in time series.
"""
import numpy as np
import pandas as pd

def report_ts_max(
    data: pd.Series
) -> dict:
    """
    Report the value and time of first maximum.
    """
    am = np.argmax(data.values)
    return {
        'value': data.values[am],
        'datetime': str(data.index[am])
    }

def report_ts_min(
    data: pd.Series
) -> dict:
    """
    Report the value and time of first minimum.
    """
    am = np.argmin(data.values)
    return {
        'value': data.values[am],
        'datetime': str(data.index[am])
    }
