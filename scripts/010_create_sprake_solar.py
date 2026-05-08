"""
Create a default solar resource file for the Sprake model.

This only needs to be a placeholder whilst we validate.
Assume at venue 72, St Asaph
(53.25535, -3.47697)
"""

import pandas as pd
import pvlib

from config import settings

if __name__ == '__main__':
    import os

    lat = float(settings.get('SprakeValidationLat'))
    lon = float(settings.get('SprakeValidationLon'))

    start_time = pd.Timestamp(settings.get('SprakeStartDatetime'), tz='utc')
    end_time = pd.Timestamp(settings.get('SprakeEndDatetime'), tz='utc')
    
    # Mean irradiance data over hour at the half-hour point
    pvg_data, pvg_meta = pvlib.iotools.get_pvgis_hourly(
        lat,
        lon,
        start = start_time,
        end = end_time - pd.Timedelta(0.5, 'h'),
        components=False,
        raddatabase='PVGIS-ERA5'
    )

    location = pvlib.location.Location(lat, lon)

    solarpos = location.get_solarposition(pvg_data.index)

    odata = pvg_data.join(solarpos)

    odata.to_csv(
        os.path.join(
            settings.get('SprakeDataLoc'),
            'default_irradiance.csv'
        )
    )
