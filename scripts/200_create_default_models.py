import contextlib
import importlib
import json
import pickle
from pathlib import Path
import random
import uuid

from common import setup_script_env
setup_script_env()


@contextlib.contextmanager
def seeded_uuid4(seed: str):
    """Make uuid.uuid4 return a reproducible sequence, seeded by `seed`.

    Components and variables take a random uuid4 when they are created, so without this the artifacts differ on every
    run, and the check in 201_validate_default_model_artifacts.py, which compares bytes, could never pass. Each module
    has its own seed, so that adding a module does not change the artifacts of the others.
    """
    rng = random.Random(seed)
    original = uuid.uuid4
    uuid.uuid4 = lambda: uuid.UUID(int = rng.getrandbits(128), version = 4)
    try:
        yield
    finally:
        uuid.uuid4 = original


if __name__ == '__main__':
    creation_functions_dir = Path(__file__).parent / 'default_model_creation_functions'

    for module_path in sorted(creation_functions_dir.glob('*.py')):
        if module_path.name == '__init__.py':
            continue

        module = importlib.import_module(
            f'default_model_creation_functions.{module_path.stem}'
        )

        with seeded_uuid4(module_path.stem):
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
