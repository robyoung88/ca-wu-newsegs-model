"""Registers and associated for the various dispatch functions"""
import logging
logger = logging.getLogger(__name__)

import copy
from dataclasses import dataclass, field
import json
from typing import Any, Callable, Optional, Protocol, Sequence, cast

from dash.development.base_component import Component as DashComponent
from useful_types import SequenceNotStr

from newsegsmodelapp.components.serialisable_dataclass import SerialisableDataclass
from newsegsmodelapp.types import LayoutConfiguration, Page
from newsegsmodelframework.core.location.location import Location
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegsvariable.lightweight_variable import FullLightweightVariable
from newsegsmodelapp.backend.db import db_tables as tbls

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
        KeyError: if a page with the same id is already registered.
    """
    page_id = page.id
    if page_id in PAGE_REGISTER:
        raise KeyError(f'A Page already exists for page_id {page_id}')
    PAGE_REGISTER[page_id] = page
    add_page_layout_configuration(page.default_configuration, page.id)

def get_page(page_id: str):
    """Get a page by id.

    Raises `KeyError` if it is not registered.

    Args:
        page_id: Id of the page.

    Returns:
        The page.
    """
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
    """Register the class of the layout configuration of a page.

    Raises `TypeError` if a different class has already been registered for the page.

    Args:
        configuration_class: Class of the layout configuration.
        page_name: Name (id) of the page.
    """
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
    """Register the layout configuration of a page for a model type.

    Raises:
        KeyError: if the page already has a configuration for a (non-default) model type.
    """
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
    """Get the layout configuration of a page for a model type.

    The configuration registered for the model type; otherwise a copy of the default configuration of the page for that model type. Raises `KeyError` if the page has no default configuration.

    Args:
        page_name: Name (id) of the page.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The configuration (a copy for the default model type).
    """
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

# REVIEW (unreferenced): no references to `get_page_layout_configuration_class` found in src/, scripts/ or data/.
def get_page_layout_configuration_class(page_name: str):
    """Get the class of the layout configuration of a page.

    Args:
        page_name: Name (id) of the page.

    Returns:
        The class.
    """
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
    calling_dict [dict[str, Any]] - a dict of other keyword arguments to the calling function: the values of the
        other inputs, `editor_ids` (the ids of the associated `input-group-editor` containers) and `app_state`
    active_project_id [str]
    project_provider [NewsegsProjectProviderInterface]
    return_dict [dict[str, Any]] - A dict of updates to output components of input_container_callbacks.react_to_input_change

It should return (modified) return_dict including:
    input_values
    header_children
    trigger_data
    editor_children
    summary_refresh - set when a value is saved or the sharing changes, to redraw the sharing summary
and any other elements that are included in the call.
"""

def register_input_handler(purpose: str, type_: str | None = None, model_type: str = 'default'):
    """Decorator which registers a function which handles a change in an input.

    Keyed by the purpose and type of the triggering component, and the model type. See `INPUT_HANDLERS` for the arguments and return of the function.

    A function registered for a model type other than `default` is also registered as the `default` for the key, if there is none yet, so that other model types fall back to it. Raises `KeyError` if a function is already registered for the key under a model type other than `default`.

    Args:
        purpose: The purpose of the triggering component (the `purpose` field of its id).
        type_: The type of the triggering component (the `type` field of its id), or None for any.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The decorator.
    """
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
    """Get the handler of a change in an input.

    Falls back to the `default` model type. Raises `KeyError` if nothing is found.

    Args:
        purpose: The purpose of the triggering component (the `purpose` field of its id).
        type_: The type of the triggering component (the `type` field of its id), or None for any.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The handler function.
    """
    getter = _three_param_key_getter_with_fallback(INPUT_HANDLERS, return_type_description = 'input handler') # pyright: ignore[reportArgumentType]
    return getter(purpose, type_, model_type)


# -------------------------------------------------------------------------
# MAIN RUNNING PROCEDURES
# -------------------------------------------------------------------------

@dataclass
class Postactions(SerialisableDataclass):
    """What to undertake after a request has completed.

    Attributes:
        action_type: The name of the request which, when complete, triggers the actions.
        run_procedures: Names of the run procedures to start.
        postprocess_procedures: Postprocess procedures to start, as `(name, model_type)`.
        table_draw_artists: Table draw procedures to start, as `(name, model_type)`.
    """
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
    """A request for a procedure to be run in the background.

    Requests are written to the database by the front end, and executed by a worker.

    Attributes:
        request_id: Id of the request in the database.
        request_type: Name of the procedure to run; selects the registered run procedure.
        trigger_request_id: Id of the request whose completion triggered this one, if any.
        trigger_request_type: Type of the request whose completion triggered this one.
        run_id: Id of the run which is executing the request.
        request_label: Description of the request, for display.
        request_class: `run`, `postprocess` or `tabledraw`.
        project_id: Id of the project that the request concerns.
        model_type: The model type of the project.
        payload: JSON string of the arguments of the procedure.
        status: Status of the request.
        background_procedure: Whether the request is executed by a worker rather than the front end.
    """
    request_id: int = -1
    request_type: str = ''
    
    trigger_request_id: int = -1
    trigger_request_type: str = ''
    
    run_id: int = -1
    
    request_label: str = ''
    request_class: str = 'run'

    project_id: str = ''
    model_type: str = 'default'
    
    payload: str = ''
    status: tbls.REQUEST_STATUS = 'AWAITING DISPATCH'
    
    background_procedure: bool = True 

class RunRequestHandler(Protocol):
    """Protocol of a function which creates a `RunRequest` for a project, e.g. in response to a user action.
    """
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
        def wrapped(request: RunRequest, *args, **kwargs):
            logger.info(
                'Run procedure %s for Request ID = %d; initiated - Run ID = %d; Triggering Request ID = %d; Project ID = %s;', 
                name, request.request_id, request.run_id, request.trigger_request_id, request.project_id
            )
            rval = func(request, *args, **kwargs)
            logger.info(
                'Run procedure %s for Request ID = %d; completed with message %s - Run ID = %d; Triggering Request ID = %d; Project ID = %s;', 
                name, request.request_id, rval, request.run_id, request.trigger_request_id, request.project_id
            )
            return rval
        RUN_PROCEDURE_REGISTER[name] = wrapped
        for trig in triggers:
            pa = POST_ACTION_REGISTER.setdefault(trig, Postactions(trig))
            pa.run_procedures.add(name)
        return wrapped
    return decorated

# -------------------------------------------------------------------------
# POSTPROCESS
# -------------------------------------------------------------------------

@dataclass
class PostprocessRequest(RunRequest):
    """A `RunRequest` for a postprocessing procedure, created when another request completes.
    """
    request_class: str = 'postprocess'

class PostprocessRequestHandler(Protocol):
    """Protocol of a function which creates a `PostprocessRequest` when another request completes.
    """
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
    """Decorator which registers a postprocessing procedure.

    Keyed by the name of the procedure and the model type. The procedure is wrapped so that it logs when it starts and completes. Each of `triggers` is the name of a request whose completion starts the procedure (via `POST_ACTION_REGISTER`). See `POSTPROCESS_REGISTER` for the arguments of the procedure.

    A function registered for a model type other than `default` is also registered as the `default` for the key, if there is none yet, so that other model types fall back to it. Raises `KeyError` if a function is already registered for the key under a model type other than `default`.

    Args:
        name: Name of the object.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.
        triggers: Names of the requests whose completion triggers the procedure.

    Returns:
        The decorator.
    """
    key = (name, model_type)
    if isinstance(triggers, str):
        triggers = [triggers]
    def decorated(func):
        if model_type != 'default':
            if key in POSTPROCESS_REGISTER:
                raise KeyError(f'Postprocess procedure already exists for key {key}')
        def wrapped(request: RunRequest, *args, **kwargs):
            logger.info(
                'Postprocess procedure %s for Request ID = %d; initiated - Run ID = %d; Triggering Request ID = %d; Project ID = %s;', 
                name, request.request_id, request.run_id, request.trigger_request_id, request.project_id
            )
            rval = func(request, *args, **kwargs)
            logger.info(
                'Postprocess procedure %s for Request ID = %d; completed with message %s - Run ID = %d; Triggering Request ID = %d; Project ID = %s;', 
                name, request.request_id, rval, request.run_id, request.trigger_request_id, request.project_id
            )
            return rval
        POSTPROCESS_REGISTER[key] = wrapped
        for trig in triggers:
            pa = POST_ACTION_REGISTER.setdefault(trig, Postactions(trig))
            pa.postprocess_procedures.add(key)

        key_default = (key[0], 'default')
        if key_default not in POSTPROCESS_REGISTER:
            POSTPROCESS_REGISTER[key_default] = wrapped
            for trig in triggers:
                pa = POST_ACTION_REGISTER.setdefault(trig, Postactions(trig))
                pa.postprocess_procedures.add(key_default)
        return wrapped
    return decorated

def get_postprocess_procedure(procedure: str, request: RunRequest):
    """Get the postprocessing procedure for a request.

    The procedure registered for the model type of the request, otherwise the `default`. Raises `KeyError` if there is none.

    Args:
        procedure: Name of the procedure.
        request: The request which triggered the procedure.

    Returns:
        The procedure.
    """
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
    """A `RunRequest` for a table drawing procedure, created when another request completes.
    """
    request_class: str = 'tabledraw'

class TableDrawRequestHandler(Protocol):
    """Protocol of a function which creates a `TableDrawRequest` when another request completes.
    """
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
    """Decorator which registers a procedure which draws the data of a table.

    Keyed by the table section and the model type. The procedure is wrapped so that it logs when it starts and completes. Each of `triggers` is the name of a request whose completion starts the procedure (via `POST_ACTION_REGISTER`). See `TABLE_DRAW_REGISTER` for the arguments of the procedure.

    A function registered for a model type other than `default` is also registered as the `default` for the key, if there is none yet, so that other model types fall back to it. Raises `KeyError` if a function is already registered for the key under a model type other than `default`.

    Args:
        name: Name of the object.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.
        triggers: Names of the requests whose completion triggers the procedure.

    Returns:
        The decorator.
    """
    key = (name, model_type)
    if isinstance(triggers, str):
        triggers = [triggers]
    def decorated(func):
        if model_type != 'default':
            if key in TABLE_DRAW_REGISTER:
                raise KeyError(f'Table draw artist already exists for key {key}')
        def wrapped(request: RunRequest, *args, **kwargs):
            logger.info(
                'Table draw procedure %s for Request ID = %d; initiated - Run ID = %d; Triggering Request ID = %d; Project ID = %s;', 
                name, request.request_id, request.run_id, request.trigger_request_id, request.project_id
            )
            rval = func(request, *args, **kwargs)
            logger.info(
                'Table draw procedure %s for Request ID = %d; completed with message %s - Run ID = %d; Triggering Request ID = %d; Project ID = %s;', 
                name, request.request_id, rval, request.run_id, request.trigger_request_id, request.project_id
            )
            return rval
        TABLE_DRAW_REGISTER[key] = wrapped
        for trig in triggers:
            pa = POST_ACTION_REGISTER.setdefault(trig, Postactions(trig))
            pa.table_draw_artists.add(key)

        key_default = (key[0], 'default')
        if key_default not in TABLE_DRAW_REGISTER:
            TABLE_DRAW_REGISTER[key_default] = wrapped
            for trig in triggers:
                pa = POST_ACTION_REGISTER.setdefault(trig, Postactions(trig))
                pa.table_draw_artists.add(key_default)
        return wrapped
    return decorated

def get_table_draw(table_section: str, request: RunRequest):
    """Get the table drawing procedure for a table section.

    The procedure registered for the model type of the request, otherwise the `default`. Raises `KeyError` if there is none.

    Args:
        table_section: Name of the table section.
        request: The request which triggered the procedure.

    Returns:
        The procedure.
    """
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
    """Register the mapping of subindices to the names of the items of a table.

    Keyed by the table section and the model type. A map registered for a model type other than `default` is also the default, if there is none yet. Raises `KeyError` if one is already registered for the key.

    Args:
        map_: Dictionary mapping subindices to names.
        name: Name of the object.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The map.
    """
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
    """Get the mapping of subindices to the names of the items of a table.

    Falls back to the `default` model type. Raises `KeyError` if there is none.

    Args:
        table_section: Name of the table section.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The map.
    """
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
    """Decorator which registers a function which retrieves a custom table from the results provider.

    Keyed by the table section and the model type. See `TABLE_GETTER_REGISTER`.

    A function registered for a model type other than `default` is also registered as the `default` for the key, if there is none yet, so that other model types fall back to it. Raises `KeyError` if a function is already registered for the key under a model type other than `default`.

    Args:
        name: Name of the object.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.
        triggers: Names of the requests whose completion triggers the procedure.

    Returns:
        The decorator.
    """
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
    """Get the function which retrieves a table.

    Falls back to the `default` model type. Raises `KeyError` if there is none.

    Args:
        table_section: Name of the table section.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The function.
    """
    proc = TABLE_GETTER_REGISTER.get((table_section, model_type))
    if proc is None:
        proc = TABLE_GETTER_REGISTER.get((table_section, 'default'))

    if proc is None:
        raise KeyError(f'Table getter for {table_section} not found - available table getter procedures are {[x[0] for x in TABLE_GETTER_REGISTER.keys()]}')

    return proc


# REVIEW (unreferenced): no references to `trigger_name_clash` found in src/, scripts/ or data/.
def trigger_name_clash(purpose: str) -> bool:
    """Whether a purpose is also the name of a run, postprocess or table draw request.

    Used to avoid ambiguity between components and requests that share a name.

    Args:
        purpose: The purpose of the triggering component (the `purpose` field of its id).

    Returns:
        True if the name clashes.
    """
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
    """Decorator which registers a function which creates the input fields of an input container.

    Keyed by the supersection (page or group of inputs), the section (`None` for all) and the model type.

    A function registered for a model type other than `default` is also registered as the `default` for the key, if there is none yet, so that other model types fall back to it. Raises `KeyError` if a function is already registered for the key under a model type other than `default`.

    Args:
        supersection: The supersection (e.g. the page or group of inputs).
        section: The section.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The decorator.
    """
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
    """Get the function which creates the input fields of an input container.

    If there is nothing for the exact key, falls back to the `default` model type, then the generic section (`ALL`), then both. Raises `KeyError` if nothing is found.

    Args:
        supersection: The supersection (e.g. the page or group of inputs).
        section: The section.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The function.
    """
    getter = _three_param_key_getter_with_fallback(
        INPUT_CONTAINER_CONTENT_CREATORS,
        return_type_description = 'content creation function'
    )
    return cast(
        Callable[[str, NewsegsProjectProviderInterface], list[DashComponent]],
        getter(supersection, section, model_type)
    )


INPUT_EDITOR_CONTENT_CREATORS: dict[
    tuple[str, str | None, str],
    Callable[[
        str,
        str,
        NewsegsProjectProviderInterface
    ], list[DashComponent]]] = {}
"""Register of functions to create the content of an input's editor, built when its row is opened.

Keyed by a tuple of:
    supersection [str] - e.g. dsa, deterministic
    section [str | None] - e.g. gen_input
    model_type [str]

Functions take the variable id, the active project id and the project provider, and return the children of the
`input-group-editor` container (see `components.input_components.create_lazy_input_details`).
"""

def register_input_editor_content_creator(supersection: str, section: str | None, model_type: str):
    """Decorator which registers a function which creates the content of an input's editor.

    Keyed by the supersection, the section (`None` for all) and the model type. See `INPUT_EDITOR_CONTENT_CREATORS` for the arguments and return of the function.

    A function registered for a model type other than `default` is also registered as the `default` for the key, if there is none yet, so that other model types fall back to it. Raises `KeyError` if a function is already registered for the key under a model type other than `default`.

    Args:
        supersection: The supersection (e.g. the page or group of inputs).
        section: The section.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The decorator.
    """
    section = section if section else 'ALL'
    key = (supersection, section, model_type)
    def decorated(func):
        if model_type != 'default':
            if key in INPUT_EDITOR_CONTENT_CREATORS:
                raise KeyError(f'Input editor content creation function already exists for {key}')
        INPUT_EDITOR_CONTENT_CREATORS[key] = func
        key_default = (key[0], key[1], 'default')
        if key_default not in INPUT_EDITOR_CONTENT_CREATORS:
            INPUT_EDITOR_CONTENT_CREATORS[key_default] = func
        return func
    return decorated

def get_input_editor_content_creator(
    supersection: str,
    section: str | None,
    model_type: str = 'default'
) -> Callable[[str, str, NewsegsProjectProviderInterface], list[DashComponent]]:
    """Get the function which creates the content of an input's editor.

    If there is nothing for the exact key, falls back to the `default` model type, then the generic section (`ALL`), then both. Raises `KeyError` if nothing is found.

    Args:
        supersection: The supersection (e.g. the page or group of inputs).
        section: The section.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The function.
    """
    getter = _three_param_key_getter_with_fallback(
        INPUT_EDITOR_CONTENT_CREATORS,
        return_type_description = 'input editor content creation function'
    )
    return cast(
        Callable[[str, str, NewsegsProjectProviderInterface], list[DashComponent]],
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
    """Decorator which registers a function which creates the header of a section of inputs.

    Keyed by the supersection, the section (`None` for all) and the model type.

    A function registered for a model type other than `default` is also registered as the `default` for the key, if there is none yet, so that other model types fall back to it. Raises `KeyError` if a function is already registered for the key under a model type other than `default`.

    Args:
        supersection: The supersection (e.g. the page or group of inputs).
        section: The section.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The decorator.
    """
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
    """Get the function which creates the header of a section of inputs.

    If there is nothing for the exact key, falls back to the `default` model type, then the generic section (`ALL`), then both. Raises `KeyError` if nothing is found.

    Args:
        supersection: The supersection (e.g. the page or group of inputs).
        section: The section.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The function.
    """
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
        FullLightweightVariable
    ], list[DashComponent]]] = {}
"""Register of functions to create header elements for a single input.

Keyed by a tuple of:
    supersection [str] - e.g. deterministic, dsa.
    section [str | None] - e.g. bc_input
    model_type [str]

Functions take the variable id as string and the variable or up-to-date FullLightweightVariable.
"""

def register_single_input_header_content_creator(
    supersection: str, section: str | None, model_type: str
):
    """Decorator which registers a function which creates the header of a single input.

    Keyed by the supersection, the section (`None` for all) and the model type.

    A function registered for a model type other than `default` is also registered as the `default` for the key, if there is none yet, so that other model types fall back to it. Raises `KeyError` if a function is already registered for the key under a model type other than `default`.

    Args:
        supersection: The supersection (e.g. the page or group of inputs).
        section: The section.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The decorator.
    """
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
    """Get the function which creates the header of a single input.

    If there is nothing for the exact key, falls back to the `default` model type, then the generic section (`ALL`), then both. Raises `KeyError` if nothing is found.

    Args:
        supersection: The supersection (e.g. the page or group of inputs).
        section: The section.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The function.
    """
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
    """Decorator which registers a function which creates the content of a result container.

    Keyed by the result key, the section (`None` for all) and the model type.

    A function registered for a model type other than `default` is also registered as the `default` for the key, if there is none yet, so that other model types fall back to it. Raises `KeyError` if a function is already registered for the key under a model type other than `default`.

    Args:
        key_: The key.
        section: The section.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The decorator.
    """
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
    """Get the function which creates the content of a result container.

    If there is nothing for the exact key, falls back to the `default` model type, then the generic section (`ALL`), then both. Raises `KeyError` if nothing is found.

    Args:
        key_: The key.
        section: The section.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The function.
    """
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
    """Decorator which registers a function which creates the header of a section of results.

    Keyed by the result key, the section (`None` for all) and the model type.

    A function registered for a model type other than `default` is also registered as the `default` for the key, if there is none yet, so that other model types fall back to it. Raises `KeyError` if a function is already registered for the key under a model type other than `default`.

    Args:
        key_: The key.
        section: The section.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The decorator.
    """
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
    """Get the function which creates the header of a section of results.

    If there is nothing for the exact key, falls back to the `default` model type, then the generic section (`ALL`), then both. Raises `KeyError` if nothing is found.

    Args:
        key_: The key.
        section: The section.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The function.
    """
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
    """Decorator which registers a function which draws a feedback graph.

    Keyed by the figure key and the model type.

    A function registered for a model type other than `default` is also registered as the `default` for the key, if there is none yet, so that other model types fall back to it. Raises `KeyError` if a function is already registered for the key under a model type other than `default`.

    Args:
        figure_key: Key of the figure.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The decorator.
    """
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
    """Get the function which draws a feedback graph.

    Falls back to the `default` model type. Raises `KeyError` if there is none.

    Args:
        figure_key: Key of the figure.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The function.
    """
    key = (figure_key, model_type)
    artist = FEEDBACK_GRAPH_ARTISTS.get(key)
    if artist:
        return artist
    key = (figure_key, 'default')
    return FEEDBACK_GRAPH_ARTISTS[key]


# -------------------------------------------------------------------------
# ENVIRONMENTAL FEEDBACK
# -------------------------------------------------------------------------

class EnvironmentDataSource(Protocol):
    """The environmental data shown as feedback on a site, for a model type.

    The data are fetched on request (by the user), not when a site is chosen, as fetching is
    slow; once fetched they are cached, so that the artists can draw them.

    Each method takes the location of the site and the focussed metamodel (a `NewsegsMetaModel`).
    The location is that of the site selector, which the metamodel may not yet hold. The data
    should be those that a run of the metamodel at the site uses (such as at the heights of its
    generators, and over its run period), so that they are fetched once for both.
    """
    def is_available(self, location: Location, metamodel: Any) -> bool:
        """Whether all the data for a site are cached, so that the feedback can be drawn."""
        ...

    def is_pending(self, location: Location, metamodel: Any) -> bool:
        """Whether the data for a site are being fetched, by this or another process."""
        ...

    def fetch(self, location: Location, metamodel: Any) -> None:
        """Fetch and cache the data for a site.

        Raises:
            EnvironmentDataUnavailableError: if the data cannot be obtained.
        """
        ...

ENVIRONMENT_DATA_SOURCES: dict[str, EnvironmentDataSource] = {}
"""Register of the sources of environmental feedback data, keyed by model type.

A model type without a source shows no environmental feedback.
"""

def register_environment_data_source(source: EnvironmentDataSource, model_type: str):
    """Register the source of environmental feedback data of a model type.

    Raises `KeyError` if one is already registered for the model type.

    Args:
        source: The data source.
        model_type: The model type (e.g. `sprakeloc`).
    """
    if model_type in ENVIRONMENT_DATA_SOURCES:
        raise KeyError(f'Environment data source already exists for model type {model_type}')
    ENVIRONMENT_DATA_SOURCES[model_type] = source

def get_environment_data_source(model_type: str) -> EnvironmentDataSource | None:
    """Get the source of environmental feedback data of a model type.

    Args:
        model_type: The model type.

    Returns:
        The data source; None if the model type has none.
    """
    return ENVIRONMENT_DATA_SOURCES.get(model_type)

EnvironmentFeedbackArtist = Callable[[Location, Sequence[tuple[str, Location]], Any], Any]
"""Draws an item of environmental feedback from cached data. Takes the location of the site, the
names and locations of the other sites of the project, and the focussed metamodel, and returns the
children of the item.
"""

ENVIRONMENT_FEEDBACK_ARTISTS: dict[tuple[str, str], EnvironmentFeedbackArtist] = {}
"""Register of functions drawing the items of environmental feedback.

Keyed by a tuple of:
    item key [str]
    model_type [str]
"""

def register_environment_feedback_artist(item_key: str, model_type: str):
    """Decorator which registers a function which draws an item of environmental feedback.

    The function must draw only from cached data: it is called once the data source of the model
    type says the data are available.

    A function registered for a model type other than `default` is also registered as the
    `default` for the key, if there is none yet. Raises `KeyError` if a function is already
    registered for the key under a model type other than `default`.

    Args:
        item_key: Key of the item.
        model_type: The model type (e.g. `sprakeloc`); `default` for the fallback.

    Returns:
        The decorator.
    """
    key = (item_key, model_type)
    def decorated(func: EnvironmentFeedbackArtist):
        if model_type != 'default' and key in ENVIRONMENT_FEEDBACK_ARTISTS:
            raise KeyError(f'Environment feedback artist already exists for key {key}')
        ENVIRONMENT_FEEDBACK_ARTISTS[key] = func
        ENVIRONMENT_FEEDBACK_ARTISTS.setdefault((item_key, 'default'), func)
        return func
    return decorated

def get_environment_feedback_artist(item_key: str, model_type: str = 'default') -> EnvironmentFeedbackArtist:
    """Get the function which draws an item of environmental feedback.

    Falls back to the `default` model type. Raises `KeyError` if there is none.

    Args:
        item_key: Key of the item.
        model_type: The model type.

    Returns:
        The function.
    """
    artist = ENVIRONMENT_FEEDBACK_ARTISTS.get((item_key, model_type))
    if artist:
        return artist
    return ENVIRONMENT_FEEDBACK_ARTISTS[(item_key, 'default')]
