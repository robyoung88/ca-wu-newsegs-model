import importlib
import shutil
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit(
            'Usage: 201_validate_default_model_artifacts.py '
            '<baseline-data-dir> <artifact-output-dir>'
        )

    generation_root = Path(__file__).resolve().parent.parent
    baseline_data_dir = Path(sys.argv[1]).resolve()
    artifact_output_dir = Path(sys.argv[2]).resolve()
    creation_functions_dir = (
        generation_root / 'scripts' / 'default_model_creation_functions'
    )
    sys.path.insert(0, str(generation_root / 'src'))
    sys.path.insert(0, str(generation_root / 'scripts'))

    artifact_output_dir.mkdir(parents=True, exist_ok=True)
    mismatches = []
    artifact_names = []

    for module_path in sorted(creation_functions_dir.glob('*.py')):
        if module_path.name == '__init__.py':
            continue

        module = importlib.import_module(
            f'default_model_creation_functions.{module_path.stem}'
        )
        artifact_names.extend(
            (
                f'{module.model_file_name}.pickle',
                f'{module.finance_file_name}.pickle',
                f'{module.variable_file_name}.json',
            )
        )

    for name in artifact_names:
        generated_path = generation_root / 'data' / name
        baseline_path = baseline_data_dir / name

        if not generated_path.is_file():
            mismatches.append(f'{name}: generator did not produce this file')
            continue

        shutil.copy2(generated_path, artifact_output_dir / name)

        if not baseline_path.is_file():
            mismatches.append(f'{name}: file is missing from the repository data folder')
        elif generated_path.read_bytes() != baseline_path.read_bytes():
            mismatches.append(f'{name}: generated content differs from repository')

    if mismatches:
        print('Generated default-model artifacts do not match the repository:')
        for mismatch in mismatches:
            print(f'  - {mismatch}')
        return 1

    print(f'Validated {len(artifact_names)} generated default-model artifacts.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
