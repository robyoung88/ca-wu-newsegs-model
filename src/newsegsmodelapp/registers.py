"""Registers and associated for the various dispatch functions"""
from dataclasses import dataclass, field
import json
from typing import Any, Callable, Optional, Protocol, Sequence, cast

from dash.development.base_component import Component as DashComponent
import sqlalchemy as sa
from useful_types import SequenceNotStr

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
# INPUT HANDLERS
# -------------------------------------------------------------------------
INPUT_HANDLERS: dict[
    tuple[str, str, str],
    Callable[
        [dict, list[dict[str,str]], list[Any], list[dict[str,str]], list[dict[str,str]], str, NewsegsProjectProviderInterface],
        tuple[list[DashComponent], list[DashComponent], list[DashComponent]]
    ]
] = {}
"""Register of functions to handle changes in inputs.

Keyed by a tuple of:
    purpose [str] - the 'purpose' field of the id of the triggering component
    type [str] - the 'type' field of the id of the triggering component
    model_type [str]

Handler functions take:
    triggered_id [dict] - the id of the triggering component
    input_ids [list[dict]] - a list of the ids of the associated Input html elements
    input_values [list] - a llist of the values of the associated Input html elements
    header_ids [list[dict]] - a list of the ids of the associated header container html elements
    trigger_ids [list[dict]] - a list of the ids of the associated trigger dcc.Store elements
    active_project_id [str]
    project_provider [NewsegsProjectProviderInterface]

They should return a tuple of three lists:
    updates for Input values
    updates for header children
    updates for trigger data
"""

def register_input_handler(purpose: str, type_: str | None = None, model_type: str = 'default'):
    type_ = 'ALL' if type_ is None else type_
    key = (purpose, type_, model_type)
    def decorated(func):
        if model_type != 'default':
            if key in INPUT_HANDLERS:
                raise KeyError(f'Input handler already exists for key {key}')
        INPUT_HANDLERS[key] = func
        key_default = (key[0], key[1], 'default')
        if key_default not in INPUT_HANDLERS:
            INPUT_HANDLERS[key_default] = func
        return func
    return decorated

def get_input_handler(purpose: str, type_: str | None = None, model_type: str = 'default'):
    getter = _three_param_key_getter_with_fallback(INPUT_HANDLERS, return_type_description = 'input handler') # pyright: ignore[reportArgumentType]
    return getter(purpose, type_, model_type)


# -------------------------------------------------------------------------
# MAIN RUNNING PROCEDURES
# -------------------------------------------------------------------------

@dataclass
class Postactions(SerialisableDataclass):
    action_type: str
    run_procedures: set[str] = field(default_factory = set)
    postprocess_procedures: set[tuple[str, str]] = field(default_factory = set)
    table_draw_artists: set[tuple[str, str]] = field(default_factory = set)

POST_ACTION_REGISTER: dict[str, Postactions] = {}
"""Register of Postactions to undertake when triggered after a completed procedure.

Within the Postaction, each entry in the list of procedures should be the key
to identify the procedure and run creator (e.g. all strings in run_procedures should
be found in RUN_PROCEDURE_REGISTER.)
"""

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
    background_procedure: bool = False # TODO: Set to default background once the dispatcher is enabled

class RunRequestHandler(Protocol):
    def __call__(
        self,
        project_id: str,
        project_provider: NewsegsProjectProviderInterface,
        config: dict[str, Any] | None = None,
    ) -> RunRequest:
        ...

RUN_REQUEST_REGISTER: dict[str, RunRequestHandler] = {}
"""Register of functions to generate run requests.

Function arguments:
    project_id [str]
    project_provider [NewsegsProjectProviderInterface]
    calling_arguments [dict]
"""

def register_run_request(name: str,):
    """Add a run request creation function to RUN_REQUEST_REGISTER
    
    The name should correspond to the purpose of the calling component (typically an action-button).
    """
    def decorated(func):
        if name in RUN_REQUEST_REGISTER:
            raise KeyError(f'A run request creator already exists for key {name}')
        RUN_REQUEST_REGISTER[name] = func
        
        return func
    return decorated

@register_run_request('_dummyrequest')
def _(project_id: str, project_provider: NewsegsProjectProviderInterface, config: dict | None = None):
    mm_id = project_provider.get_focussed_metamodel_id(project_id)
    config = config.copy() if config else {}
    config.update({'metamodel_id': mm_id})
    return RunRequest(
        project_id = project_id,
        request_id = 'A dummy request',
        payload = json.dumps(config)
    )

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

def register_run_procedure(
    name: str,
    triggers: SequenceNotStr[str] = [],
):
    """Add a background run procedure to the register.
    
    The name should correspond to the request_type of the RunRequest
    """
    if isinstance(triggers, str):
        triggers = [triggers]
    def decorated(func):
        if name in RUN_PROCEDURE_REGISTER:
            raise KeyError(f'A run procedure already exists for key {name}')
        RUN_PROCEDURE_REGISTER[name] = func
        for trig in triggers:
            pa = POST_ACTION_REGISTER.setdefault(trig, Postactions(trig))
            pa.run_procedures.add(name)
        return func
    return decorated

# -------------------------------------------------------------------------
# POSTPROCESS
# -------------------------------------------------------------------------

@dataclass
class PostprocessRequest(RunRequest):
    request_class: str = 'postprocess'
    trigger_request_type: str = ''

class PostprocessRequestHandler(Protocol):
    def __call__(
        self,
        trigger_request: RunRequest,
        config: dict[str, Any] | None = None,
    ) -> PostprocessRequest:
        ...

POSTPROCESS_REQUEST_REGISTER: dict[str, PostprocessRequestHandler] = {}
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
def register_postprocess_procedure(
        name: str, model_type: str = 'default',
        triggers: SequenceNotStr[str] = []
    ):
    key = (name, model_type)
    if isinstance(triggers, str):
        triggers = [triggers]
    def decorated(func):
        if model_type != 'default':
            if key in POSTPROCESS_REGISTER:
                raise KeyError(f'Postprocess procedure already exists for key {key}')
        POSTPROCESS_REGISTER[key] = func
        for trig in triggers:
            pa = POST_ACTION_REGISTER.setdefault(trig, Postactions(trig))
            pa.postprocess_procedures.add(key)

        key_default = (key[0], 'default')
        if key_default not in POSTPROCESS_REGISTER:
            POSTPROCESS_REGISTER[key_default] = func
            for trig in triggers:
                pa = POST_ACTION_REGISTER.setdefault(trig, Postactions(trig))
                pa.postprocess_procedures.add(key_default)
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

class TableDrawRequestHandler(Protocol):
    def __call__(
        self,
        trigger_request: RunRequest,
        config: dict[str, Any] | None = None,
    ) -> TableDrawRequest:
        ...

TABLE_DRAW_REQUEST_REGISTER: dict[str, TableDrawRequestHandler] = {}
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

def register_table_draw(
    name: str, model_type: str = 'default',
    triggers: SequenceNotStr[str] = []
):
    key = (name, model_type)
    if isinstance(triggers, str):
        triggers = [triggers]
    def decorated(func):
        if model_type != 'default':
            if key in TABLE_DRAW_REGISTER:
                raise KeyError(f'Table draw artist already exists for key {key}')
        TABLE_DRAW_REGISTER[key] = func
        for trig in triggers:
            pa = POST_ACTION_REGISTER.setdefault(trig, Postactions(trig))
            pa.table_draw_artists.add(key)

        key_default = (key[0], 'default')
        if key_default not in TABLE_DRAW_REGISTER:
            TABLE_DRAW_REGISTER[key_default] = func
            for trig in triggers:
                pa = POST_ACTION_REGISTER.setdefault(trig, Postactions(trig))
                pa.table_draw_artists.add(key_default)
        return func
    return decorated

def get_table_draw(table_section: str, request: RunRequest):
    proc = TABLE_DRAW_REGISTER.get((table_section, request.model_type))
    if proc is None:
        proc = TABLE_DRAW_REGISTER.get((table_section, 'default'))

    if proc is None:
        raise KeyError(f'Table draw for {table_section} not found - available table draw procedures are {[x[0] for x in TABLE_DRAW_REGISTER.keys()]}')

    return proc

TABLE_SUBINDEX_MAPS: dict[
    tuple[str, str],
    dict[int, str]
] = {}
"""Register of mappings from subindices to result item names.

Keyed by a tuple of:
    (table_section_name [str], model_type[str])
"""

def register_table_subindex_map(map_: dict, name: str, model_type: str = 'default'):
    key = (name, model_type)
    if model_type != 'default':
        if key in TABLE_SUBINDEX_MAPS:
            raise KeyError(f'Table subindex map already exists for key {key}')
    TABLE_SUBINDEX_MAPS[key] = map_
    key_default = (key[0], 'default')
    if key_default not in TABLE_SUBINDEX_MAPS:
        TABLE_SUBINDEX_MAPS[key_default] = map_
    return map_

def get_table_subindex_map(table_section:str, model_type: str = 'default'):
    key = (table_section, model_type)
    map_ = TABLE_SUBINDEX_MAPS.get(key)
    if map_ is None:
        key = (table_section, 'default')
        
        map_ = TABLE_SUBINDEX_MAPS.get(key)
        if not map_:
            raise KeyError(f'{key} not found in table subindex maps - available values are {TABLE_SUBINDEX_MAPS.keys()}')
    return map_


TABLE_GETTER_REGISTER: dict[
    tuple[str, str],
    Callable[[str, dict, NewsegsProjectProviderInterface, NewsegsResultProviderInterface], Any]
] = {}
"""Register functions for retrieving custom tables from the results provider using a dictionary of options associated with the component(s)

Keyed by a tuple of:
    (table_section_name [str], model_type[str])
"""

def register_table_getter(
    name: str, model_type: str = 'default',
    triggers: SequenceNotStr[str] = []
):
    key = (name, model_type)
    if isinstance(triggers, str):
        triggers = [triggers]
    def decorated(func):
        if model_type != 'default':
            if key in TABLE_GETTER_REGISTER:
                raise KeyError(f'Table getter already exists for key {key}')
        TABLE_GETTER_REGISTER[key] = func
        
        key_default = (key[0], 'default')
        if key_default not in TABLE_GETTER_REGISTER:
            TABLE_GETTER_REGISTER[key_default] = func
            
        return func
    return decorated

def get_table_getter(table_section: str, model_type: str = 'default'):
    proc = TABLE_GETTER_REGISTER.get((table_section, model_type))
    if proc is None:
        proc = TABLE_GETTER_REGISTER.get((table_section, 'default'))

    if proc is None:
        raise KeyError(f'Table getter for {table_section} not found - available table getter procedures are {[x[0] for x in TABLE_GETTER_REGISTER.keys()]}')

    return proc


def trigger_name_clash(purpose: str) -> bool:
    return purpose in [*RUN_REQUEST_REGISTER.keys(), *POSTPROCESS_REQUEST_REGISTER.keys(), *TABLE_DRAW_REQUEST_REGISTER.keys()]

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
        raise KeyError(f'No {return_type_description} found for key {key} - available keys are {list(dictionary_.keys())}')
    
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
        return_type_description = 'input header content creation function'
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
# Result Layouts
# -------------------------------------------------------------------------
RESULT_CONTAINER_CONTENT_CREATORS: dict[
    tuple[str, str | None, str],
    Callable[[
        str,
        NewsegsProjectProviderInterface
    ], list[DashComponent]]] = {}
"""Register of functions to create results contents within result-containers.

Keyed by a tuple of:
    key_ [str] - e.g. postproc_generation
    section [str | None] - e.g. postprocess
    model_type [str]
"""

def register_result_container_content_creator(key_: str, section: str | None, model_type: str):
    section = section if section else 'ALL'
    key = (key_, section, model_type)
    def decorated(func):
        if model_type != 'default':
            if key in RESULT_CONTAINER_CONTENT_CREATORS:
                raise KeyError(f'Result container content creation function already exists for {key}')
        RESULT_CONTAINER_CONTENT_CREATORS[key] = func
        key_default = (key[0], key[1], 'default')
        if key_default not in RESULT_CONTAINER_CONTENT_CREATORS:
            RESULT_CONTAINER_CONTENT_CREATORS[key_default] = func
        return func
    return decorated

def get_result_container_content_creator(
    key_: str, 
    section: str | None, 
    model_type: str = 'default'
) -> Callable[[str, NewsegsProjectProviderInterface], list[DashComponent]]:
    getter = _three_param_key_getter_with_fallback(
        RESULT_CONTAINER_CONTENT_CREATORS,
        return_type_description = 'content creation function'
    )
    return cast(
        Callable[[str, NewsegsProjectProviderInterface], list[DashComponent]],
        getter(key_, section, model_type)
    )

RESULT_SECTION_HEADER_CONTENT_CREATORS: dict[
    tuple[str, str | None, str],
    Callable[[
        str,
        NewsegsProjectProviderInterface,
        NewsegsResultProviderInterface,
        bool
    ], list[DashComponent]]] = {}
"""Register of functions to create feedback elements within `result-section-header`s.

Keyed by a tuple of:
    key [str] - e.g. postproc_generation
    section [str | None] - e.g. postprocess
    model_type [str]
"""

def register_result_section_header_content_creator(key_: str, section: str | None, model_type: str):
    section = section if section else 'ALL'
    key = (key_, section, model_type)
    def decorated(func):
        if model_type != 'default':
            if key in RESULT_SECTION_HEADER_CONTENT_CREATORS:
                raise KeyError(f'Result header content creation function already exists for {key}')
        RESULT_SECTION_HEADER_CONTENT_CREATORS[key] = func
        key_default = (key[0], key[1], 'default')
        if key_default not in RESULT_SECTION_HEADER_CONTENT_CREATORS:
            RESULT_SECTION_HEADER_CONTENT_CREATORS[key_default] = func
        return func
    return decorated

def get_result_section_header_content_creator(
    key_: str, 
    section: str | None, 
    model_type: str = 'default'
) -> Callable[[str, NewsegsProjectProviderInterface, NewsegsResultProviderInterface, Optional[bool]], list[DashComponent]]:
    getter = _three_param_key_getter_with_fallback(
        RESULT_SECTION_HEADER_CONTENT_CREATORS,
        return_type_description = 'result header content creation function'
    )
    return cast(
        Callable[[str, NewsegsProjectProviderInterface, NewsegsResultProviderInterface, Optional[bool]], list[DashComponent]], 
        getter(key_, section, model_type)
    )


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
