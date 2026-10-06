"""Registers and associated for the various dispatch functions"""
import copy
from dataclasses import asdict, dataclass, field
import json
from typing import Any, Callable, Optional, Protocol, Sequence, cast

from dash.development.base_component import Component as DashComponent
import sqlalchemy as sa
from useful_types import SequenceNotStr

from newsegsmodelapp.components.serialisable_dataclass import SerialisableDataclass
from newsegsmodelapp.types import LayoutConfiguration, Page
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsproject import NewsegsProject, NewsegsProjectProviderInterface

# -------------------------------------------------------------------------
# APP PAGE REGISTER
# -------------------------------------------------------------------------
PAGE_REGISTER: dict[str, Page] = {}
"""Register of Page objects, containing layouts of app pages.

Key:
    page_id [str] - The last element of the page url (i.e. https://{site}/{model_type}/{page_id})
"""

def add_page(page: Page):
    """
    Add a Page to the PAGE_REGISTER

    Raises:
        KeyError - if name already present in register
    """
    page_id = page.id
    if page_id in PAGE_REGISTER:
        raise KeyError(f'A Page already exists for page_id {page_id}')
    PAGE_REGISTER[page_id] = page
    add_page_layout_configuration(page.default_configuration, page.id)

def get_page(page_id: str):
    page = PAGE_REGISTER.get(page_id)
    if page is None:
        raise KeyError(f'Page {page_id} is not present in register - available pages are {PAGE_REGISTER.keys()}')
    return page

PAGE_LAYOUT_CONFIGURATION_REGISTER: dict[tuple[str, str], LayoutConfiguration] = {}
PAGE_LAYOUT_CONFIGURATION_CLASS_REGISTER: dict[str, type] = {}

def add_page_layout_configuration_class(
    configuration_class,
    page_name: str,
):
    if page_name in PAGE_LAYOUT_CONFIGURATION_CLASS_REGISTER:
        if configuration_class != PAGE_LAYOUT_CONFIGURATION_CLASS_REGISTER[page_name]:
            raise TypeError(f'LayoutConfiguration class has already been set for page {page_name} and is incompatible with {configuration_class}')
        else:
            return
    PAGE_LAYOUT_CONFIGURATION_CLASS_REGISTER[page_name] = configuration_class

def add_page_layout_configuration(
    configuration: LayoutConfiguration, 
    page_name: str,
    model_type: str = 'default'
):
    key = (page_name, model_type)
    if model_type != 'default':
        if key in PAGE_LAYOUT_CONFIGURATION_REGISTER:
            raise KeyError(f'Page layout configuration already exists for key {key}')
    add_page_layout_configuration_class(type(configuration), page_name)
    PAGE_LAYOUT_CONFIGURATION_REGISTER[key] = copy.copy(configuration)
    if model_type != 'default':
        key_default = (page_name, 'default')
        if key_default not in PAGE_LAYOUT_CONFIGURATION_REGISTER:
            config = copy.copy(configuration)
            config.model_type = 'default'
            PAGE_LAYOUT_CONFIGURATION_REGISTER[key] = config

def get_page_layout_configuration(
    page_name: str,
    model_type: str = 'default'
):
    key_default = (page_name, 'default')
    default_config = PAGE_LAYOUT_CONFIGURATION_REGISTER.get(key_default)
    if not default_config:
        raise KeyError(f'No default page configuration for page {page_name} - available pages are {set(x[0] for x in PAGE_LAYOUT_CONFIGURATION_REGISTER.keys())}')
    if model_type == 'default' :
        return copy.copy(default_config)

    key = (page_name, model_type)
    specific_config = PAGE_LAYOUT_CONFIGURATION_REGISTER.get(key)

    if not specific_config:
        conf = copy.copy(default_config)
        conf.model_type = model_type
        return conf
    return specific_config

def get_page_layout_configuration_class(page_name: str):
    return PAGE_LAYOUT_CONFIGURATION_CLASS_REGISTER.get(page_name, type(LayoutConfiguration))

# -------------------------------------------------------------------------
# INPUT HANDLERS
# -------------------------------------------------------------------------
INPUT_HANDLERS: dict[
    tuple[str, str, str],
    Callable[
        [
            dict, 
            list[dict[str,str]], 
            list[dict[str,str]], 
            list[dict[str,str]],
            dict[str, Any],
            str,
            NewsegsProjectProviderInterface,
            dict[str, Any],
        ],
        dict[str, Any],
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
    header_ids [list[dict]] - a list of the ids of the associated header container html elements
    trigger_ids [list[dict]] - a list of the ids of the associated trigger dcc.Store elements
    calling_dict [dict[str, Any]] - a dict of other keyword arguments to the calling function
    active_project_id [str]
    project_provider [NewsegsProjectProviderInterface]
    return_dict [dict[str, Any]] - A dict of updates to output components of input_container_callbacks.react_to_input_change

It should return (modified) return_dict including:
    input_values
    header_children
    trigger_data
and any other elements that are included in the call.
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
    request_id: int = 0
    run_id: int = 0
    trigger_run_id: int = -1
    project_id: str = ''
    model_type: str = 'default'
    request_label: str = ''
    request_class: str = 'run'
    request_type: str = ''
    payload: str = ''
    status: str = ''
    progress: float = 0.0
    progress_message: str = ''
    cancel_requested: bool = False
    background_procedure: bool = True 

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
        request_label = 'A dummy request',
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

