"""
Set up a Sprake finance wrapper per the external validation model, then save out the config
"""
import json
import pickle

from common import setup_script_env
setup_script_env()
from newsegsmodelframework.util import jsonfuncs

from newsegsmodelframework.newsegsfinance import sprakefinance

if __name__ == '__main__':
    fnc = sprakefinance.SprakeFinance.from_none()

    # Apply resident discount
    fnc.resident_var_per_unit = 0.35 * (1 - 0.15)

    # Apply discount factors
    fnc.benefit_discount_rate = 0.035
    fnc.cost_discount_rate = 0.035

    d1 = fnc.to_dict_repr()
    with open('data/sprakemodel-validation-finance-config.json', 'w') as f:
        json.dump(d1, f, sort_keys=False, indent=4)

    with open('data/sprakemodel-validation-finance-config.pickle', 'wb') as f:
        fnc.set_state_exclusion_policy('excluded')
        pickle.dump(fnc, f)
        fnc.set_state_exclusion_policy('excluded_and_components')
