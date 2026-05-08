"""
Create a default wind resource file for the Sprake model.

This only needs to be a placeholder whilst we validate.
A 20 m hub height at venue 72, St Asaph
(53.25535, -3.47697)
is appropriate.
"""
import numpy as np
import pandas as pd

from config import settings

from src.util import wind_resource_helpers

if __name__ == '__main__':
    import os
    lat = float(settings.get('SprakeValidationLat'))
    lon = float(settings.get('SprakeValidationLon'))
    hub_height = 20.0
    dt_start=settings.get('SprakeStartDatetime')
    dt_stop=settings.get('SprakeEndDatetime')
    
    rng = np.random.default_rng(260423)
    
    wind_resource = wind_resource_helpers.get_wind_at_site(
        lat, lon,
        rng,
        dt_start = dt_start,
        dt_stop = dt_stop,
        site_heights = [hub_height]
    )

    wind_out = (
        wind_resource
        .assign(
            # Shift the times to the mid of their averaging interval
            time = lambda df: df['time'] - pd.Timedelta(15, 'm'),
            # 
            datetime = lambda df: df['time'].dt.ceil('h')
        )
        .loc[:, ['datetime', 'hub_height', 'ws_hub']]
        .groupby(['datetime', 'hub_height'])
        .mean()
        .reset_index()
    )
    
    wind_out.to_csv(
        os.path.join(
            settings.get('SprakeDataLoc'),
            'default_wind_speeds.csv'
        ),
        index=False
    )

