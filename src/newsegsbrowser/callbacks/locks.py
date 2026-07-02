from typing import Sequence

from useful_types import SequenceNotStr


def _ok_run_x(
    lock_ids: list[dict], 
    lock_values: list[bool], 
    target: str | SequenceNotStr[str]
) -> bool:
    ok = True
    if not isinstance(target, str) and isinstance(target, Sequence):
        for lock_nm, lock_val in zip(lock_ids, lock_values):
            if lock_nm.get('target') in target:
                ok = ok and lock_val
                if not ok:
                    return False
    else:
        for lock_nm, lock_val in zip(lock_ids, lock_values):
            if lock_nm.get('target') == target:
                ok = ok and lock_val
                if not ok:
                    return False
    return ok    

def ok_run_model(
    lock_ids: list[dict], 
    lock_values: list[bool], 
) -> bool:
    return _ok_run_x(lock_ids, lock_values, 'model-run')

def ok_run_finance(
    lock_ids: list[dict], 
    lock_values: list[bool], 
) -> bool:
    return _ok_run_x(lock_ids, lock_values, 'finance-run')
