import pandas as pd

from common import setup_script_env
setup_script_env()

from config import settings

from newsegscs.ev_profiles import characterise_dates_evprofile

if __name__ == '__main__':
    import os
    dates = pd.date_range('2017-01-01T00:30:00','2017-12-31T23:30:00',freq='h',tz='utc')
    
    oframe = characterise_dates_evprofile(dates)

    fn = os.path.join(
            settings.get('SprakeExcelValidationLoc'),
            'Input sheets',
            'sprake_profile_ev_days.csv'
        )
    
    oframe.to_csv(fn, index=False)
    
    # Model dates
    dates = pd.date_range(
        settings.get('SprakeStartDatetime'),
        settings.get('SprakeEndDatetime'),
        freq='h',
        tz='utc'
    )

    oframe = characterise_dates_evprofile(dates -pd.Timedelta(30,'m'))
    oframe = (
        oframe
        .assign(datetime = dates)
    )

    fn = os.path.join(
            settings.get('SprakeExcelValidationLoc'),
            'Input sheets',
            'sprake_model_ev_days.csv'
        )
    
    oframe.to_csv(fn, index=False)

    # No difference
    #import holidays
    #dates = pd.date_range('2017-01-01T00:30:00','2017-12-31T23:30:00',freq='h',tz='utc')
    
    #oframe = characterise_dates_evprofile(dates, hols=holidays.country_holidays('GB', subdiv='ENG'))

    #fn = os.path.join(
    #        r'C:\Users\YoungR2\OneDrive - Wrexham University\Model',
    #        'sprake_profile_ev_days_england.csv'
    #    )
    
    #oframe.to_csv(fn, index=False)
