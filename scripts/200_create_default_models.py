import importlib
import json
import pickle
from pathlib import Path

from common import setup_script_env
setup_script_env()


if __name__ == '__main__':
    creation_functions_dir = Path(__file__).parent / 'default_model_creation_functions'

    for module_path in sorted(creation_functions_dir.glob('*.py')):
        if module_path.name == '__init__.py':
            continue

        module = importlib.import_module(
            f'default_model_creation_functions.{module_path.stem}'
        )

        mdl = module.create_energy_model()
        fnc = module.create_finance_model()
        variables = module.create_variable_list(mdl, fnc)

        with open(f'data/{module.model_file_name}.pickle', 'wb') as f:
            mdl.set_state_exclusion_policy('excluded')
            pickle.dump(mdl, f)
            mdl.set_state_exclusion_policy('excluded_and_components')

        with open(f'data/{module.finance_file_name}.pickle', 'wb') as f:
            fnc.set_state_exclusion_policy('excluded')
            pickle.dump(fnc, f)
            fnc.set_state_exclusion_policy('excluded_and_components')

        variables_ser = [var.to_dict() for var in variables]
        with open(f'data/{module.variable_file_name}.json', 'w') as f:
            json.dump(variables_ser, f, sort_keys=False, indent=4)
