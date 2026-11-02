"""
Feedback on whether process results are up to date with their inputs.

Staleness is recorded per configuration (metamodel) and process in the
process_staleness table: input handlers mark the processes that a change
meaningfully affects, and run procedures record their completion.
"""
from collections.abc import Iterable
from typing import Literal

from dash import html
import numpy as np

from newsegsmodelapp.backend.db import db_staleness
from newsegsmodelapp.backend.db.db_staleness import PROCESSES
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

ProcessState = Literal['ok', 'stale', 'not-run']

INDICATOR_TYPE = 'results-staleness-indicator'
TOOLTIP_TYPE = 'results-staleness-tooltip'

RESULT_HEADER_CLASS = 'result-header-single-config'

# Every process evaluates the model around the deterministic values
DETERMINISTIC_CASCADE = PROCESSES

PROCESS_LABELS = {
    'deterministic': 'Deterministic results',
    'dsa': 'DSA',
    'psa': 'PSA',
    'optim': 'Optimisation',
}

# Processes whose indicators cover every configuration; others cover the focussed one
_PROJECT_SCOPE_PROCESSES = {'deterministic'}

# Results identifying runs completed before staleness was recorded:
# (result type, function giving the holding component id from a lightweight metamodel)
_LEGACY_RESULTS = {
    'deterministic': ('postproc_generation', lambda lmm: lmm.model.table_config.id),
    'dsa': ('dsa_single_metamodel', lambda lmm: lmm.table_config.id),
    'psa': ('psa_single_metamodel', lambda lmm: lmm.table_config.id),
}

_INDICATOR_CLASSES: dict[ProcessState, str] = {
    'ok': 'feedback-strip staleness-indicator-ok',
    'stale': 'feedback-strip staleness-indicator-warning',
    'not-run': 'feedback-strip staleness-indicator-error',
}

def get_process_states(lmms: Iterable, process: str) -> dict[str, ProcessState]:
    """State of the process for each lightweight metamodel, keyed by metamodel id"""
    lmms = list(lmms)
    times = db_staleness.get_process_times([x.id for x in lmms], [process])

    with_results = set()
    unrecorded = [x for x in lmms if times.get((x.id, process), (None, None))[1] is None]
    if unrecorded and process in _LEGACY_RESULTS:
        result_type, get_component_id = _LEGACY_RESULTS[process]
        mm_by_component = {get_component_id(x): x.id for x in unrecorded}
        with_results = {
            mm_by_component[x] for x in db_staleness.results_exist(result_type, mm_by_component)
        }

    states: dict[str, ProcessState] = {}
    for lmm in lmms:
        changed_ns, last_run_ns = times.get((lmm.id, process), (None, None))
        if last_run_ns is None:
            if lmm.id not in with_results:
                states[lmm.id] = 'not-run'
                continue
            last_run_ns = 0 # Results predate staleness recording
        states[lmm.id] = 'stale' if changed_ns is not None and changed_ns > last_run_ns else 'ok'
    return states

def metamodels_using_variable(lproj, var_uid: str) -> list[str]:
    """Ids of the project's metamodels that hold the variable instance"""
    return [mm.id for mm in lproj.metamodels if var_uid in set(mm.variables.values())]

def processes_affected(
    deterministic: bool = False,
    dsa: bool = False,
    psa: bool = False,
    optim: bool = False,
) -> set[str]:
    """The processes made stale by changes to the flagged kinds of input"""
    processes = set(DETERMINISTIC_CASCADE) if deterministic else set()
    for process, changed in (('dsa', dsa), ('psa', psa), ('optim', optim)):
        if changed:
            processes.add(process)
    return processes

def _differs(a, b) -> bool:
    try:
        return bool(a != b)
    except ValueError: # Array-valued parameters
        return not np.array_equal(a, b)

def _try_get(getter):
    try:
        return getter()
    except TypeError:
        return None

def processes_affected_by_variable_swap(old_var, new_var) -> set[str]:
    """
    The processes made stale by a configuration switching from one variable
    instance to another, e.g. on changing how the variable is shared.
    """
    dsa = _differs(old_var.dsa_selected, new_var.dsa_selected) or (
        new_var.dsa_show and any(
            _differs(_try_get(lambda: old_var.get_dsa_value(bound, True)), _try_get(lambda: new_var.get_dsa_value(bound, True)))
            for bound in ('lower', 'upper')
        )
    )
    psa = _differs(old_var.psa_selected, new_var.psa_selected) or (
        new_var.psa_show and _differs(_try_get(old_var.get_std), _try_get(new_var.get_std))
    )
    return processes_affected(
        deterministic = _differs(old_var.deterministic_value, new_var.deterministic_value),
        dsa = dsa,
        psa = psa,
        optim = _differs(old_var.optim_selected, new_var.optim_selected),
    )

def result_header_class_name(state: ProcessState | None, focussed: bool) -> str:
    """Class name for a configuration's results section header"""
    class_name = RESULT_HEADER_CLASS
    if state != 'ok':
        class_name += ' stale'
    if not focussed:
        class_name += ' unfocussed'
    return class_name

def create_staleness_indicator(page_type: str, process: str) -> list:
    """A strip and tooltip giving feedback on whether the process results are up to date"""
    indicator_id = {'type': INDICATOR_TYPE, 'page': page_type, 'process': process}
    return [
        html.Div(id = indicator_id, className = 'feedback-strip'),
        dbc.Tooltip(
            f'Checking {PROCESS_LABELS[process]}...',
            id = {'type': TOOLTIP_TYPE, 'page': page_type, 'process': process},
            target = indicator_id,
        ),
    ]

def indicator_feedback(lproj, process: str) -> tuple[str, str]:
    """Class name and tooltip text for a process staleness indicator"""
    label = PROCESS_LABELS[process]

    if process not in _PROJECT_SCOPE_PROCESSES:
        lmm = lproj.metamodels[lproj.focussed_metamodel_index]
        state = get_process_states([lmm], process)[lmm.id]
        match state:
            case 'not-run':
                text = f'{label} has not been run for the selected configuration.'
            case 'stale':
                text = f'{label} results are out of date for the selected configuration; inputs have changed since it was last run.'
            case _:
                text = f'{label} results are up to date for the selected configuration.'
        return _INDICATOR_CLASSES[state], text

    states = get_process_states(lproj.metamodels, process)
    numbers = {state: [str(i + 1) for i, x in enumerate(lproj.metamodels) if states[x.id] == state] for state in ('not-run', 'stale')}
    messages = []
    if numbers['not-run']:
        messages.append(f'have not been run for configuration(s) {", ".join(numbers["not-run"])}')
    if numbers['stale']:
        messages.append(f'are out of date for configuration(s) {", ".join(numbers["stale"])}')

    if not messages:
        return _INDICATOR_CLASSES['ok'], f'{label} are up to date for all configurations.'
    state: ProcessState = 'not-run' if numbers['not-run'] else 'stale'
    return _INDICATOR_CLASSES[state], f'{label} {" and ".join(messages)}.'
