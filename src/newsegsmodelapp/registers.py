"""Registers and associated for the various dispatch functions"""
from dataclasses import dataclass
from typing import Any, Callable

import sqlalchemy as sa

from newsegsmodelapp.components.resultmeta import ResultMeta
from newsegsmodelapp.components.serialisable_dataclass import SerialisableDataclass
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject import NewsegsProject, NewsegsProjectProviderInterface

# -------------------------------------------------------------------------
# MAIN RUNNING PROCEDURES
# -------------------------------------------------------------------------

@dataclass
class RunRequest(SerialisableDataclass):
    run_id: int = 0
    project_id: str = ''
    model_type: str = 'default'
    request_id: str = ''
    request_type: str = ''
    payload: str = ''
    status: str = ''
    progress: float = 0.0
    progress_message: str = ''
    cancel_requested: bool = False

RUN_REQUEST_REGISTER: dict[str, Callable[[NewsegsProject, sa.Engine], RunRequest]] = {}
"""Register of functions to generate run requests.

Function arguments:
    proj [NewsegsProject]
    engine [sqlalchemy engine]
"""

def register_run_request(name: str):
    """Add a run request creation function to RUN_REQUEST_REGISTER
    
    The name should correspond to the key of the calling component.
    """
    def decorated(func):
        RUN_REQUEST_REGISTER[name] = func
        return func
    return decorated

RUN_PROCEDURE_REGISTER: dict[str, Callable[[
    RunRequest,
    NewsegsProjectProviderInterface,
    NewsegsResultProviderInterface,
    int,
    Callable,
    Callable
], str]] = {}
"""Register of functions to undertake in background procedures.

Function arguments:
    The request [RunRequest]
    A project provider [NewsegsProjectProviderInterface]
    A results handler [NewsegsResultProviderInterface]
    The run id [int]
    Progress callback function [Callable[float, float, str]]
    Progress cancelled function [Callable[[], bool]]

Function returns:
    Status message ('ok')
"""

def register_run_procedure(name: str):
    """Add a background run procedure to the register.
    
    The name should correspond to the request_type of the RunRequest
    """
    def decorated(func):
        RUN_PROCEDURE_REGISTER[name] = func
        return func
    return decorated


# -------------------------------------------------------------------------
# POSTPROCESS
# -------------------------------------------------------------------------

POSTPROCESS_REGISTER: dict[
    tuple[str, str], 
    Callable[[
        RunRequest, 
        NewsegsProjectProviderInterface, 
        NewsegsResultProviderInterface,
        int,
        Callable,
        Callable
    ], str]] = {}
"""Register of functions to undertake postprocessing procedures.

Keyed by a tuple of:
    (process_name [str], model_type[str])
For any given process, it is advised that a 'default' model type key is provided as a fallback.

Function arguments:
    The original procedure request for which this is postprocessing [RunRequest]
    A project provider [NewsegsProjectProviderInterface]
    A results handler [NewsegsResultProviderInterface]
    The run id [int]
    Progress callback function [Callable[float, float, str]]
    Progress cancelled function [Callable[[], bool]]

Function returns:
    Status message ('ok')
"""
def register_postprocess_procedure(name_type: tuple[str, str]):
    def decorated(func):
        POSTPROCESS_REGISTER[name_type] = func
        key_default = (name_type[0], 'default')
        if key_default not in POSTPROCESS_REGISTER:
            POSTPROCESS_REGISTER[key_default] = func
        return func
    return decorated

def get_postprocess_procedure(procedure: str, request: RunRequest):
    proc = POSTPROCESS_REGISTER.get((procedure, request.model_type))
    if proc is None:
        proc = POSTPROCESS_REGISTER.get((procedure, 'default'))

    if proc is None:
        raise KeyError(f'Postprocess procedure {procedure} not found - available procedures are {[x[0] for x in POSTPROCESS_REGISTER.keys()]}')

    return proc


LOADER_REGISTER: dict[str, Callable[[str], Any]] =  {}
"""Register of functions to retrieve results from a directory.

Function arguments:
    File path [str]

Function returns:
    Loaded results

Notes:
    The function is memoised, so results should not re-use the same path.
"""

def register_loader(name: str):
    """Add a loader to the register.
    
    The name should correspond to the suffix (extension) of the results file
    """
    def decorated(func):
        LOADER_REGISTER[name] = func
        return func
    return decorated

# -------------------------------------------------------------------------
# DRAWING
# -------------------------------------------------------------------------

TABLE_DRAW_REGISTER: dict[str, Callable[[tuple[ResultMeta, ...]], Any]] = {}
"""Register of functions to create table data given a tuple of live results.

Function arguments:
    tuple of ResultMeta objects

Function returns:
    Table as dash components.

Notes:
    The function is memoised, so results should not re-use the same path.
"""

def register_table_draw(name: str):
    """Add a table draw function to the register.
    
    The name should correspond to the key of the table container id.
    """
    def decorated(func):
        TABLE_DRAW_REGISTER[name] = func
        return func
    return decorated

FIGURE_DRAW_REGISTER: dict[str, Callable[[tuple[ResultMeta, ...]], Any]] = {}
"""Register of functions to create figures given a tuple of live results.

Function arguments:
    tuple of ResultMeta objects

Function returns:
    Figures as dash components.

Notes:
    The function is memoised, so results should not re-use the same path.
"""

def register_figure_draw(name: str):
    """Add a figure draw function to the register.
    
    The name should respond the the key of the graph id.
    """
    def decorated(func):
        FIGURE_DRAW_REGISTER[name] = func
        return func
    return decorated
