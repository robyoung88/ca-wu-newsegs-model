"""Extract the results of the independently coded Sprake validation workbook into gold files in `data/`.

The Sprake model is validated against `Sprake_model_validation.xlsx`, an Excel implementation of the model that
is not in the repository. This script, run on a computer with access to the workbook, saves the results that the
tests compare against, so that the tests (and CI) do not need the workbook:

    data/sprake_validation/meters.parquet  Hourly meters (`Raw` sheet), indexed by UTC datetime.
    data/sprake_validation/totals.json     Totals over the run, including the finance figures (`Totals` sheet).

Run it again, and commit the files, whenever the workbook changes.

Usage:
    python scripts/210_extract_sprake_validation_results.py [WORKBOOK]

WORKBOOK defaults to `Sprake_model_validation.xlsx` in the `SprakeExcelValidationLoc` setting, which is defined in
the `[testing]` section of `settings.toml`.
"""
import argparse
import json
import os
from pathlib import Path

import pandas as pd

from common import setup_script_env
setup_script_env()

# SprakeExcelValidationLoc is only defined for testing; spraketest, a variant of it, is left in place.
if os.environ.get('NEWSEGS_ENV', '').strip().lower() not in ('testing', 'spraketest'):
    os.environ['NEWSEGS_ENV'] = 'testing'

from config import settings
from newsegsmodelframework import STATICDATA

WORKBOOK_NAME = 'Sprake_model_validation.xlsx'
OUTPUT_DIR = STATICDATA / 'sprake_validation'
METERS_FILE = OUTPUT_DIR / 'meters.parquet'
TOTALS_FILE = OUTPUT_DIR / 'totals.json'


def default_workbook() -> Path:
    """The validation workbook in the `SprakeExcelValidationLoc` setting."""
    location = settings.get('SprakeExcelValidationLoc')
    if location is None:
        raise SystemExit('SprakeExcelValidationLoc is not set; pass the path to the workbook instead.')
    return Path(location) / WORKBOOK_NAME


def read_meters(workbook: pd.ExcelFile) -> pd.DataFrame:
    """The hourly meters of the `Raw` sheet, indexed by UTC datetime."""
    return (
        pd.read_excel(workbook, sheet_name = 'Raw', header = 0, parse_dates = ['datetime'])
        .assign(datetime = lambda df: df['datetime'].dt.tz_localize('utc'))
        .set_index('datetime')
    )


def read_totals(workbook: pd.ExcelFile) -> dict[str, float]:
    """The totals of the `Totals` sheet, by name."""
    totals = pd.read_excel(workbook, sheet_name = 'Totals', header = 0, index_col = 'name')
    return {str(name): float(value) for name, value in totals['value'].items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = __doc__, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('workbook', nargs = '?', type = Path, help = 'Path to the validation workbook.')
    args = parser.parse_args()

    workbook_path = args.workbook or default_workbook()
    print(f'Reading {workbook_path}')
    with pd.ExcelFile(workbook_path) as workbook:
        meters = read_meters(workbook)
        totals = read_totals(workbook)

    OUTPUT_DIR.mkdir(parents = True, exist_ok = True)
    meters.to_parquet(METERS_FILE)
    with open(TOTALS_FILE, 'w', encoding = 'utf-8') as f:
        json.dump(totals, f, indent = 4)
        f.write('\n')

    print(f'Wrote {len(meters)} rows of {list(meters.columns)} to {METERS_FILE}')
    print(f'Wrote {len(totals)} totals to {TOTALS_FILE}')
