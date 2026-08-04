"""Provides methods for obtaining New European Wind Atlas data."""
from newa.get_newa_data import (
    get_newa_micro_point, 
    get_newa_meso_point, 
    get_newa_meso_ts_point,
)

__all__ = [
    'get_newa_micro_point',
    'get_newa_meso_point',
    'get_newa_meso_ts_point'
]