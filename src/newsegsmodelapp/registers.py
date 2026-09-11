"""Registers and associated for the various dispatch functions"""
from dataclasses import dataclass
from typing import Any, Callable, cast

from dash.development.base_component import Component as DashComponent
import sqlalchemy as sa

from newsegsmodelapp.components.serialisable_dataclass import SerialisableDataclass
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsproject import NewsegsProject, NewsegsProjectProviderInterface

# -------------------------------------------------------------------------
# APP PAGE REGISTER
# -------------------------------------------------------------------------
PAGE_LAYOUT_REGISTER: dict[str, Callable[[dict], DashComponent]] = {}
"""Register of functions to return page contents.

Function arguments:
    app_state [dict]
"""

def register_page_layout(name: str):
    """Add a page layout creation function to PAGE_LAYOUT_REGISTER
    
    The name should correspond to the page path (after the model specifier)

    Raises:
        KeyError - if name already present in register
    """
    def decorated(func):
        if name in PAGE_LAYOUT_REGISTER:
            raise KeyError(f'A page layout function already exists for name {name}')
        PAGE_LAYOUT_REGISTER[name] = func
        return func
    return decorated

# -------------------------------------------------------------------------
# MAIN RUNNING PROCEDURES
# -------------------------------------------------------------------------

@dataclass
class RunRequest(SerialisableDataclass):
    run_id: int = 0
    project_id: str = ''
    model_type: str = 'default'
    request_id: str = ''
    request_class: str = 'run'
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

@dataclass
class PostprocessRequest(RunRequest):
    request_class: str = 'postprocess'
    trigger_request_type: str = ''

POSTPROCESS_REQUEST_REGISTER: dict[str, Callable[[RunRequest], PostprocessRequest]] = {}
"""Register of functions to generate postprocess requests.

Function arguments:
    request [RunRequest]
"""

def register_postprocess_request(name: str):
    """Add a postprocess request creation function to POSTPROCESS_REQUEST_REGISTER
    
    The name should correspond to the postprocess type / request_class.
    """
    def decorated(func):
        if name in POSTPROCESS_REQUEST_REGISTER:
            raise KeyError(f'A postprocess request function already exists for name {name}')
        POSTPROCESS_REQUEST_REGISTER[name] = func
        return func
    return decorated

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


# -------------------------------------------------------------------------
# TABLES
# -------------------------------------------------------------------------

@dataclass
class TableDrawRequest(RunRequest):
    request_class: str = 'tabledraw'
    trigger_request_type: str = ''
    ann_hori_toggle: bool = False

TABLE_DRAW_REQUEST_REGISTER: dict[str, Callable[[RunRequest], TableDrawRequest]] = {}
"""Register of functions to generate table draw requests.

Function arguments:
    request [RunRequest]
"""

def register_table_draw_request(name: str):
    """Add a table draw request creation function to TABLE_DRAW_REQUEST_REGISTER
    
    The name should correspond to the table field.
    """
    def decorated(func):
        if name in TABLE_DRAW_REQUEST_REGISTER:
            raise KeyError(f'A table draw request function already exists for name {name}')
        TABLE_DRAW_REQUEST_REGISTER[name] = func
        return func
    return decorated

TABLE_DRAW_REGISTER: dict[
    tuple[str, str],
    Callable[[
        RunRequest,
        NewsegsProjectProviderInterface,
        NewsegsResultProviderInterface,
        int,
        Callable,
        Callable,
    ], str]] = {}
"""Register of functions to create table data after a Run.

Keyed by a tuple of:
    (table_section_name [str], model_type[str])
For any given table section, it is advised that a 'default' model type key is provided as a fallback.

Function arguments:
    The original procedure request for which this is postprocessing [RunRequest]
    A project provider [NewsegsProjectProviderInterface]
    A results handler [NewsegsResultProviderInterface]
    The run id [int]
    Progress callback function [Callable[float, float, str]]
    Progress cancelled function [Callable[[], bool]]
    The annual/horizon toggle [bool]

Function returns:
    Status message ('ok')
"""

def register_table_draw(name_type: tuple[str, str]):
    def decorated(func):
        TABLE_DRAW_REGISTER[name_type] = func
        key_default = (name_type[0], 'default')
        if key_default not in TABLE_DRAW_REGISTER:
            TABLE_DRAW_REGISTER[key_default] = func
        return func
    return decorated

def get_table_draw(table_section: str, request: RunRequest):
    proc = TABLE_DRAW_REGISTER.get((table_section, request.model_type))
    if proc is None:
        proc = TABLE_DRAW_REGISTER.get((table_section, 'default'))

    if proc is None:
        raise KeyError(f'Table draw for {table_section} not found - available table draw procedures are {[x[0] for x in TABLE_DRAW_REGISTER.keys()]}')

    return proc


# -------------------------------------------------------------------------
# Input Layouts
# -------------------------------------------------------------------------
INPUT_CONTAINER_CONTENT_CREATORS: dict[
    tuple[str, str | None, str],
    Callable[[
        str,
        NewsegsProjectProviderInterface
    ], list[DashComponent]]] = {}
"""Register of functions to create Input fields within input-containers.

Keyed by a tuple of:
    supersection [str] - e.g. dsa, model-inputs etc
    section [str | None] - e.g. gen-inputs
    model_type [str]
"""

def register_input_container_content_creator(supersection: str, section: str | None, model_type: str):
    section = section if section else 'ALL'
    key = (supersection, section, model_type)
    def decorated(func):
        if model_type != 'default':
            if key in INPUT_CONTAINER_CONTENT_CREATORS:
                raise KeyError(f'Input container content creation function already exists for {key}')
        INPUT_CONTAINER_CONTENT_CREATORS[key] = func
        key_default = (key[0], key[1], 'default')
        if key_default not in INPUT_CONTAINER_CONTENT_CREATORS:
            INPUT_CONTAINER_CONTENT_CREATORS[key_default] = func
        return func
    return decorated

def _three_param_key_getter_with_fallback(
    dictionary_: dict[tuple[str, str | None, str], Any],
    b_default: str = 'ALL',
    c_default: str = 'default',
    return_type_description: str = 'value'
):
    def f(a, b, c):
        b = b_default if b is None else b
        c = c_default if c is None else c

        key = (a, b, c)
        rval = dictionary_.get(key)
        if rval:
            return rval

        # Fallback 1 - default model
        key = (a, b, c_default)
        rval = dictionary_.get(key)
        if rval:
            return rval

        # Fallback 2 - generic section
        key = (a, b_default, c)
        rval = dictionary_.get(key)
        if rval:
            return rval

        # Fallback 3 - generic section and default model
        key = (a, b_default, c_default)
        rval = dictionary_.get(key)
        if rval:
            return rval

        key = (a, b, c)
        KeyError(f'No {return_type_description} found for key {key} - available keys are {list(INPUT_CONTAINER_CONTENT_CREATORS.keys())}')
    
    return f

def get_input_container_content_creator(
    supersection: str, 
    section: str | None, 
    model_type: str = 'default'
) -> Callable[[str, NewsegsProjectProviderInterface], list[DashComponent]]:
    getter = _three_param_key_getter_with_fallback(
        INPUT_CONTAINER_CONTENT_CREATORS,
        return_type_description = 'content creation function'
    )
    return cast(
        Callable[[str, NewsegsProjectProviderInterface], list[DashComponent]],
        getter(supersection, section, model_type)
    )


INPUT_SECTION_HEADER_CONTENT_CREATORS: dict[
    tuple[str, str | None, str],
    Callable[[
        str,
        NewsegsProjectProviderInterface
    ], list[DashComponent]]] = {}
"""Register of functions to create feedback elements within `input-section-header`s.

Keyed by a tuple of:
    supersection [str] - e.g. dsa, model-inputs etc
    section [str | None] - e.g. gen-inputs
    model_type [str]
"""

def register_input_section_header_content_creator(supersection: str, section: str | None, model_type: str):
    section = section if section else 'ALL'
    key = (supersection, section, model_type)
    def decorated(func):
        if model_type != 'default':
            if key in INPUT_SECTION_HEADER_CONTENT_CREATORS:
                raise KeyError(f'Input header content creation function already exists for {key}')
        INPUT_SECTION_HEADER_CONTENT_CREATORS[key] = func
        key_default = (key[0], key[1], 'default')
        if key_default not in INPUT_SECTION_HEADER_CONTENT_CREATORS:
            INPUT_SECTION_HEADER_CONTENT_CREATORS[key_default] = func
        return func
    return decorated

def get_input_section_header_content_creator(
    supersection: str, 
    section: str | None, 
    model_type: str = 'default'
) -> Callable[[str, NewsegsProjectProviderInterface], list[DashComponent]]:
    getter = _three_param_key_getter_with_fallback(
        INPUT_SECTION_HEADER_CONTENT_CREATORS,
        return_type_description = 'header content creation function'
    )
    return cast(
        Callable[[str, NewsegsProjectProviderInterface], list[DashComponent]], 
        getter(supersection, section, model_type)
    )


SINGLE_INPUT_HEADER_CONTENT_CREATORS: dict[
    tuple[str, str | None, str],
    Callable[[
        str,
        NewsegsMetaModel
    ], list[DashComponent]]] = {}
"""Register of functions to create header elements for a single input.

Keyed by a tuple of:
    supersection [str] - e.g. deterministic, dsa.
    section [str | None] - e.g. bc_input
    model_type [str]

Functions take the variable id as string and the containing metamodel.
"""

def register_single_input_header_content_creator(
    supersection: str, section: str | None, model_type: str
):
    section = 'ALL' if section is None else section
    key = (supersection, section, model_type)
    def decorated(func):
        if model_type != 'default':
            if key in SINGLE_INPUT_HEADER_CONTENT_CREATORS:
                raise KeyError(f'Single input header content creation already exists for {key}')
        SINGLE_INPUT_HEADER_CONTENT_CREATORS[key] = func
        key_default = (key[0], key[1], 'default')
        if key_default not in SINGLE_INPUT_HEADER_CONTENT_CREATORS:
            SINGLE_INPUT_HEADER_CONTENT_CREATORS[key_default] = func
        return func
    return decorated

def get_single_input_header_content_creator(
    supersection: str,
    section: str | None,
    model_type: str = 'default'
):
    getter = _three_param_key_getter_with_fallback(
        SINGLE_INPUT_HEADER_CONTENT_CREATORS,
        return_type_description = 'single input header content creation function'
    )
    return getter(supersection, section, model_type)

# -------------------------------------------------------------------------
# DRAWING
# -------------------------------------------------------------------------

FEEDBACK_GRAPH_ARTISTS: dict[
    tuple[str, str],
    Callable[[
        str,
        NewsegsProjectProviderInterface
    ], DashComponent]] = {}
"""Register of functions to update feedback graphs as configurations change.

Keyed by a tuple of:
    figure key [str] 
    model_type [str]

Functions take the active project id as string and a project provider.
"""

def register_feedback_graph_artist(figure_key: str, model_type: str):
    key = (figure_key, model_type)
    def decorated(func):
        if model_type != 'default':
            if key in FEEDBACK_GRAPH_ARTISTS:
                raise KeyError(f'Feedback graph artist already exists for key {key}')
        FEEDBACK_GRAPH_ARTISTS[key] = func
        key_default = (key[0], 'default')
        if key_default not in FEEDBACK_GRAPH_ARTISTS:
            FEEDBACK_GRAPH_ARTISTS[key_default] = func
        return func
    return decorated

def get_feedback_graph_artist(figure_key: str, model_type: str = 'default'):
    key = (figure_key, model_type)
    artist = FEEDBACK_GRAPH_ARTISTS.get(key)
    if artist:
        return artist
    key = (figure_key, 'default')
    return FEEDBACK_GRAPH_ARTISTS[key]

# FIGURE_DRAW_REGISTER: dict[str, Callable[[tuple[ResultMeta, ...]], Any]] = {}
# """Register of functions to create figures given a tuple of live results.

# Function arguments:
#     tuple of ResultMeta objects

# Function returns:
#     Figures as dash components.

# Notes:
#     The function is memoised, so results should not re-use the same path.
# """

# def register_figure_draw(name: str):
#     """Add a figure draw function to the register.
    
#     The name should respond the the key of the graph id.
#     """
#     def decorated(func):
#         FIGURE_DRAW_REGISTER[name] = func
#         return func
#     return decorated
