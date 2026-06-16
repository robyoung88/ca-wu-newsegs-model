import pandas as pd

from common import setup_script_env
setup_script_env()

from config import settings

from newsegscs.elexon_profiles import characterise_dates_elexon

if __name__ == '__main__':
    import os
    dates = pd.date_range(
        settings.get('SprakeStartDatetime'),
        settings.get('SprakeEndDatetime'),
        freq='h',
        tz='utc'
    )
    # Evaluate the dates 15 minutes into the past, just to ensure midnights reflect the previous day


    oframe = characterise_dates_elexon(dates -pd.Timedelta(15,'m'))
    oframe = (
        oframe
        .assign(datetime = dates)
    )

    fn = os.path.join(
            settings.get('SprakeExcelValidationLoc'),
            'Input sheets',
            'sprake_model_elexon_days.csv'
        )
    
    oframe.to_csv(fn, index=False)
    