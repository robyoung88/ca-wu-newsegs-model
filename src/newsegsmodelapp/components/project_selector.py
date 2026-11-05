"""The project selector: choosing, creating, duplicating, renaming and deleting projects, and managing their snapshots.
"""
import logging
logger = logging.getLogger(__name__)

import json
from typing import Any, cast

import dash
from dash import ALL, Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify
import numpy as np

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.components import callback_utils
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelframework.util import naming

# -----------------------------------------------
# Helper functions
# -----------------------------------------------

def fetch_project_options(
    project_provider: NewsegsProjectProviderInterface,
    model_type: str|None = None
) -> list[dict[str, Any]]:
    """Obtains available projects"""
    all_projects = project_provider.list_projects(model_type = model_type).to_dict(orient = 'list')
    if not all_projects:
        return []
    return [
        {
            'value' : str(all_projects['id'][i]),
            'label': f'{all_projects['label'][i]} [created: {all_projects['created_at'][i]}]'
        } 
        for i in range(len(all_projects['id'])-1, -1, -1)
    ]

def fetch_snapshot_options(
    project_provider: NewsegsProjectProviderInterface,
    project_id: str
) -> list[dict[str, str]]:
    """Obtains snapshots for nominated project."""
    all_snapshots = project_provider.list_project_snapshots(project_id).to_dict(orient = 'list')
    if not all_snapshots:
        return []
    return [
        {
            'value': str(all_snapshots['snapshot_id'][i]),
            'label': f'{all_snapshots['label'][i]} [created: {all_snapshots['created_at'][i]}]'
        }
        for i in range(len(all_snapshots['snapshot_id']))
    ]

def rename_project(
    project_provider: NewsegsProjectProviderInterface,
    project_id: str,
    project_name: str,
):
    """Rename a project.

    Args:
        project_provider: Provider of projects, metamodels and variables.
        project_id: Id of the project.
        project_name: The new name of the project.
    """
    project_provider.set_component_metadata(
        project_id,
        'label',
        project_name,
    )

def create_snapshot(
    project_provider: NewsegsProjectProviderInterface,
    project_id: str,
    snapshot_name: str,
) -> int:
    """Create a snapshot of a project.

    Args:
        project_provider: Provider of projects, metamodels and variables.
        project_id: Id of the project.
        snapshot_name: The label of the snapshot.

    Returns:
        The id of the snapshot.
    """
    return project_provider.create_project_snapshot(
        project_id, snapshot_name
    )

def verify_project_exists(
    project_provider: NewsegsProjectProviderInterface,
    project_id: str
) -> bool:
    """Whether a project exists.

    Args:
        project_provider: Provider of projects, metamodels and variables.
        project_id: Id of the project.

    Returns:
        True if it does.
    """
    try:
        label = project_provider.get_component_metadata(
            project_id, 'label'
        )
    except Exception as e:
        logger.exception('Failed to retrieve Project ID: %s', project_id, exc_info = True)
        return False
    return label is not None

def load_snapshot(
    project_provider: NewsegsProjectProviderInterface,
    current_project_id: str,
    snapshot_id: str
) -> str | None:
    """Restore a snapshot of the current project as a new project.

    Args:
        project_provider: Provider of projects, metamodels and variables.
        current_project_id: Id of the current project.
        snapshot_id: Id of the snapshot.

    Returns:
        The id of the new project, or None if the snapshot is not found.
    """
    int_snapshot_id = int(snapshot_id)
    all_snapshots = project_provider.list_project_snapshots(current_project_id)
    if not np.any(all_snapshots['snapshot_id'] == int_snapshot_id):
        return None
    snapshot_label = all_snapshots.loc[all_snapshots['snapshot_id']==int_snapshot_id,'label'].iloc[0]
    new_proj = project_provider.load_project_snapshot(
        current_project_id, int_snapshot_id
    )
    rename_project(project_provider, new_proj.id, f'{new_proj.name} from {snapshot_label}')
    return new_proj.id

def new_project(
    project_provider: NewsegsProjectProviderInterface,
    model_type: str
) -> str:
    """Create a new project of a model type with the factory registered for it, and store it.

    Args:
        project_provider: Provider of projects, metamodels and variables.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The id of the project.
    """
    from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES
                    
    factory = PROJECT_FACTORIES.get(model_type, PROJECT_FACTORIES['default'])

    proj = factory()
    project_provider.upsert_component(proj)
    return proj.id

def duplicate_project(
    project_provider: NewsegsProjectProviderInterface,
    current_project_id: str,
) -> str:
    """Duplicate a project and store the copy.

    Args:
        project_provider: Provider of projects, metamodels and variables.
        current_project_id: Id of the current project.

    Returns:
        The id of the copy.
    """
    new_proj = cast(
        NewsegsProject, 
        project_provider.duplicate_component(current_project_id)
    )
    project_provider.upsert_component(new_proj)
    rename_project(
        project_provider,
        new_proj.id,
        naming.copy_name(new_proj.name, project_provider.list_projects()['label'])
    )
    return new_proj.id

def rename_snapshot(
    project_provider: NewsegsProjectProviderInterface,
    snapshot_id: str,
    snapshot_name: str,
):
    """Rename a snapshot.

    Args:
        project_provider: Provider of projects, metamodels and variables.
        snapshot_id: Id of the snapshot.
        snapshot_name: The label of the snapshot.
    """
    if not isinstance(project_provider, FromDatabaseNewsegsProjectProvider):
        return
    project_provider.rename_snapshot(int(snapshot_id), snapshot_name)

def delete_project(
    project_provider: NewsegsProjectProviderInterface,
    delete_project_id: str,
    active_project_id: str,
    model_type: str,
) -> str | None:
    """Delete a project.

    Raises `ValueError` if it cannot be deleted.

    Args:
        project_provider: Provider of projects, metamodels and variables.
        delete_project_id: Id of the project to delete.
        active_project_id: Id of the active project.
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The id of the project to make active: the active one if a different project was deleted; otherwise another.
    """
    returned = project_provider.delete_component(delete_project_id)
    if returned:
        raise ValueError('Project could not be deleted')
    if delete_project_id != active_project_id:
        return active_project_id

    proj_options = fetch_project_options(project_provider, model_type)
    if proj_options:
        return proj_options[0].get('value')

    return None

def delete_snapshot(
    project_provider: NewsegsProjectProviderInterface,
    project_id: str,
    delete_snapshot_id: str
):
    """Delete a snapshot.

    Args:
        project_provider: Provider of projects, metamodels and variables.
        project_id: Id of the project.
        delete_snapshot_id: Id of the snapshot to delete.
    """
    int_dsi = int(delete_snapshot_id)
    project_provider.delete_project_snapshot(project_id, int_dsi)

# -----------------------------------------------
# Layout component
# -----------------------------------------------
def create_project_selector():
    
    """Create the project selector: choosing, creating, duplicating, renaming and deleting projects, and managing their snapshots.

    Returns:
        The layout.
    """
    def stores_and_dialogs() -> list[dash.development.base_component.Component]:
        return [
            # Delete project confirmation dialog
            dcc.ConfirmDialog(
                id = 'delete-project-confirm-dialog',
                message = 'Proceeding will delete the selected project and all saved results. Continue?'
            ),

            # Delete snapshot confirmation dialog
            dcc.ConfirmDialog(
                id = 'delete-snapshot-confirm-dialog',
                message = 'Proceeding will delete the selected snapshot and all saved results. Continue?'
            ),
        ]

    def active_project_header() -> html.Div:
        return html.Div(
            [
                html.Span(
                    [
                        html.Span("Project: ", className="text-muted me-2 fs-4"),
                        html.H2(
                            "Untitled Project",
                            id="header-project-name",
                            className="d-inline-block mb-0 me-3 fw-bold",
                        )
                    ],
                    className = 'd-flex align-items-center'
                ),
                dbc.Button(
                    DashIconify(icon="bi:list", width=18),
                    id="btn-toggle-controls",
                    color="light",
                    size="sm",
                    className="border toggle-controls",
                )
            ],
            className="d-flex align-items-center justify-content-between header",
        )

    def project_operations() -> list[dash.development.base_component.Component]:
        return [
            *project_operations_header(),
            *project_operations_inputs()
        ]

    def project_operations_inputs() -> list[dash.development.base_component.Component]:
        return [
            *project_name_input(),
            *project_load_input(),
            *project_action_buttons(),
        ]

    def snapshot_operations() -> list[dash.development.base_component.Component]:
        return [
            *snapshot_operations_header(),
            *snapshot_operations_inputs(),
        ]

    def project_operations_header() -> list[dash.development.base_component.Component]:
            return [
                html.H6("Project Management", className="fw-bold mb-3 border-bottom pb-1")
            ]

    def snapshot_operations_header() -> list[dash.development.base_component.Component]:
        return [
            html.H6("Snapshots", className="fw-bold mb-3 border-bottom pb-1"),
        ]

    def snapshot_operations_inputs() -> list[dash.development.base_component.Component]:
        return [
            *snapshot_name_input(),
            *snapshot_load_input(),
            *snapshot_action_buttons(),
        ]

    def project_name_input() -> list[dash.development.base_component.Component]:
        return [
            dbc.InputGroup(
                [
                    dbc.Input(
                        id="input-project-name",
                        placeholder="Project name",
                        type="text",
                        size="sm",
                    ),
                    dbc.Button(
                        [DashIconify(icon="bi:pencil", className="me-1"), "Rename"],
                        id = {'type': 'action-button-ps', 'key': 'rename-project'},
                        #id="btn-rename-project",
                        color="primary",
                        size="sm",
                        outline=True,
                        class_name = ACTION_BUTTON_CLASSNAME,
                        disabled=True,
                    ),
                    
                ],
                className="mb-2",
            ),
        ]

    def snapshot_name_input() -> list[dash.development.base_component.Component]:
        return [
            dbc.InputGroup(
                [
                    dbc.Input(
                        id="input-snapshot-name",
                        placeholder="Snapshot name, e.g. Before tariff change",
                        type="text",
                        size="sm",
                    ),
                    dbc.Button(
                        [DashIconify(icon="bi:camera", className="me-1"), "Create"],
                        id = {'type': 'action-button-ps', 'key': 'create-snapshot'},
                        #id="btn-create-snapshot",
                        color="primary",
                        size="sm",
                        outline=True,
                        disabled=True,
                    ),
                ],
                className="mb-2",
            ),
        ]

    def project_load_input() -> list[dash.development.base_component.Component]:
        return [
            dbc.InputGroup(
                [
                    dbc.Select(
                        id="select-load-project",
                        placeholder="Select a project",
                        size="sm",
                    ),
                    dbc.Button(
                        [DashIconify(icon="bi:box-arrow-in-right", className="me-1"), "Load"],
                        id = {'type': 'action-button-ps', 'key': 'load-project'},
                        color="info",
                        size="sm",
                        disabled=True,
                    ),
                ],
                className="mb-3",
            ), 
        ]

    def snapshot_load_input() -> list[dash.development.base_component.Component]:
        return [
            dbc.InputGroup(
                [
                    dbc.Select(
                        id="select-load-snapshot",
                        placeholder="Select a snapshot",
                        size="sm",
                    ),
                    dbc.Button(
                        [DashIconify(icon="bi:box-arrow-in-right", className="me-1"), "Load"],
                        id = {'type': 'action-button-ps', 'key': 'load-snapshot'},
                        color="info",
                        size="sm",
                        disabled=True,
                    ),
                ],
                className="mb-2",
            ),
        ]

    ACTION_BUTTON_CLASSNAME = 'action-button'

    def project_action_buttons() -> list[dash.development.base_component.Component]:
        return [
            html.Div(
                [
                    html.Div(
                        dbc.Button(
                            [DashIconify(icon="bi:file-earmark-plus", className="me-1"), "Fresh Project"],
                            id = {'type': 'action-button-ps', 'key': 'new-project'},
                            color="success",
                            size="sm",
                            class_name = ACTION_BUTTON_CLASSNAME,
                        ),
                        className = 'auto-wrap-item',
                    ),
                    html.Div(
                        dbc.Button(
                            [DashIconify(icon="bi:copy", className="me-1"), "Duplicate Project"],
                            id = {'type': 'action-button-ps', 'key': 'duplicate-project'},
                            color="primary",
                            size="sm",
                            outline=True,
                        ),
                        className = 'auto-wrap-item',
                    ),
                    html.Div(
                        dbc.Button(
                            [DashIconify(icon="bi:trash", className="me-1"), "Delete Project"],
                            id = {'type': 'action-button-ps', 'key': 'delete-project'},
                            color="danger",
                            size="sm",
                            outline=True,
                            disabled=True,
                            class_name = ACTION_BUTTON_CLASSNAME,
                        ),
                        className = 'auto-wrap-item',
                    )
                ],
                className="auto-wrap-row",
            )
        ]

    def snapshot_action_buttons() -> list[dash.development.base_component.Component]:
        return [
            html.Div(
                [
                    html.Div(
                        dbc.Button(
                            [DashIconify(icon="bi:pencil", className="me-1"), "Rename Snapshot"],
                            #id="btn-rename-snapshot",
                            id = {'type': 'action-button-ps', 'key': 'rename-snapshot'},
                            color="secondary",
                            size="sm",
                            outline=True,
                            disabled=True,
                            class_name = ACTION_BUTTON_CLASSNAME,
                        ),
                        className="auto-wrap-item",
                    ),
                    html.Div(
                        dbc.Button(
                            [DashIconify(icon="bi:trash", className="me-1"), "Delete Snapshot"],
                            id = {'type': 'action-button-ps', 'key': 'delete-snapshot'},
                            color="danger",
                            size="sm",
                            outline=True,
                            disabled=True,
                            class_name = ACTION_BUTTON_CLASSNAME,
                        ),
                        className="auto-wrap-item",
                    ),
                ],
                className="auto-wrap-row",
            )
        ]

    return dbc.Container(
        [
            dbc.Navbar(
                dbc.Container(
                    [
                        # Left side: Active project header & collapsible toggle
                        active_project_header()
                    ],
                    fluid = True,
                ),
                color="white",
                class_name="border-bottom py-2 mb-3",
            ),

            # Hidden Controls Drawer (Accordion / Collapse)
            dbc.Collapse(
                dbc.Card(
                    dbc.CardBody([
                        dbc.Row(
                            [
                                # Left column: Project Operations
                                dbc.Col(
                                    [*project_operations()],
                                    xl=6,
                                    class_name="border-end pe-4" 
                                ),

                                # Right column: Snapshot Operations
                                dbc.Col(
                                    [*snapshot_operations()],
                                    xl=6,
                                    class_name="ps-4",
                                )                                
                            ],
                        )
                        
                    ],
                    ),
                    class_name = "shadow-sm mb-3",
                ),
                id = 'collapse-controls',
                is_open = False,
            ),
            *stores_and_dialogs(),
        ],
        fluid = True,
        class_name = 'newsegs-project-selector',
    )

create_project_selector_block = create_project_selector

_PROJECT_INPUT_IDS = {'select-load-project', 'input-project-name'}
_SNAPSHOT_INPUT_IDS = {'select-load-snapshot', 'input-snapshot-name'}

def ui_state_triggers(triggers: list[callback_utils.Trigger]) -> set[str]:
    """The triggers of the project selector's state callback to act on.

    Every trigger is considered, as several may fire together, such as the active project and the app state on a
    change of page. A change of the active project resets the project and snapshot selectors and name inputs, and a
    change of the app state the project ones, so changes of those inputs in the same call are ignored.

    Args:
        triggers: The triggers of the callback.

    Returns:
        The ids of the triggers to act on.
    """
    ids = {x.id for x in triggers if isinstance(x.id, str)}
    if 'active-project-id' in ids:
        ids -= _SNAPSHOT_INPUT_IDS
    if ids & {'active-project-id', 'app-state'}:
        ids -= _PROJECT_INPUT_IDS
    return ids

def add_project_selector_callbacks(app: NewsegsDash):
    """Bind the callbacks of the project selector.

    Args:
        app: The Dash app.
    """
    @app.callback(
        Output("collapse-controls", "is_open"),
        Input("btn-toggle-controls", "n_clicks"),
        State("collapse-controls", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_controls(n_clicks, is_open):
        return not is_open if n_clicks else is_open

    def _disable_project_load_buttons(state: bool, rval):
        # As no project selected, disable the load and delete buttons
        callback_utils.update_property_by_id(
            {'type': 'action-button-ps', 'key': 'load-project'},
            'disabled',
            state,
            rval
        )
        callback_utils.update_property_by_id(
            {'type': 'action-button-ps', 'key': 'delete-project'},
            'disabled',
            state,
            rval
        )

    def _disable_project_rename_button(state: bool, rval):
        callback_utils.update_property_by_id(
                {'type': 'action-button-ps', 'key': 'rename-project'},
                'disabled',
                state,
                rval
            )

    def _disable_snapshot_rename_button(state: bool, rval):
        callback_utils.update_property_by_id(
            {'type': 'action-button-ps', 'key': 'rename-snapshot'},
            'disabled',
            state,
            rval
        )

    def _disable_snapshot_load_buttons(state: bool, rval):
        callback_utils.update_property_by_id(
            {'type': 'action-button-ps', 'key': 'load-snapshot'},
            'disabled',
            state,
            rval
        )
        callback_utils.update_property_by_id(
            {'type': 'action-button-ps', 'key': 'delete-snapshot'},
            'disabled',
            state,
            rval
        )

    def _disable_snapshot_create_button(state: bool, rval):
        callback_utils.update_property_by_id(
            {'type': 'action-button-ps', 'key': 'create-snapshot'},
            'disabled',
            state,
            rval
        )

    @app.callback(
        output = dict(
            header_project_name = Output('header-project-name', 'children'),
            project_select = dict(
                value = Output('select-load-project', 'value'),
                options = Output('select-load-project', 'options')
            ),
            snapshot_select = dict(
                value = Output('select-load-snapshot', 'value'),
                options = Output('select-load-snapshot', 'options')
            ),
            input_project_name = dict(
                value =  Output('input-project-name', 'value'),
            ),
            input_snapshot_name = dict(
                value =  Output('input-snapshot-name', 'value'),
            ),
            buttons = dict (
                button_disabled = Output({'type': 'action-button-ps', 'key': ALL}, 'disabled'),
                button_class = Output({'type': 'action-button-ps', 'key': ALL}, 'class_name'),
            )
        ),
        inputs = dict(
            active_project_id = Input('active-project-id', 'data'),
            app_state = Input('app-state', 'data'),
            select_project = Input('select-load-project', 'value'),
            select_snapshot = Input('select-load-snapshot', 'value'),
            input_project_name = Input('input-project-name', 'value'),
            input_snapshot_name = Input('input-snapshot-name', 'value'),
            
        ),
        
        prevent_initial_call = True
    )
    def update_ui_states(
        active_project_id,
        app_state,
        select_project,
        select_snapshot,
        input_project_name,
        input_snapshot_name,
    ):

        rval = callback_utils.create_noupdate_return()

        triggered = ui_state_triggers(callback_utils.get_triggers())
        if 'active-project-id' in triggered:
            rval['header_project_name'] = app.project_provider.get_component_metadata(active_project_id, 'label')['label']

            # Update snapshot selector
            all_snapshots = fetch_snapshot_options(app.project_provider, active_project_id)
            rval['snapshot_select']['options'] = all_snapshots
            rval['snapshot_select']['value'] = None

            # As no snapshot selected, disable the load, rename and delete buttons
            _disable_snapshot_load_buttons(True, rval)

            # Also clear the name input
            rval['input_snapshot_name']['value'] = None
            _disable_snapshot_create_button(True, rval)
            _disable_snapshot_rename_button(True, rval)
            
        if triggered & {'active-project-id', 'app-state'}:
            # Update project selector
            app_state = json.loads(app_state) if app_state else {}
            model_type = app_state.get('model_type', 'default')
            all_projects = fetch_project_options(app.project_provider, model_type)
            rval['project_select']['options'] = all_projects
            rval['project_select']['value'] = None

            # As no project selected, disable the load and delete buttons
            _disable_project_load_buttons(True, rval)

            # Also clear the name input
            rval['input_project_name']['value'] = None
            _disable_project_rename_button(True, rval)

        if 'select-load-project' in triggered:
            project_nominated = select_project is not None
            _disable_project_load_buttons(not(project_nominated), rval)

        if 'input-project-name' in triggered:
            new_project_name = input_project_name
            _disable_project_rename_button((new_project_name is None or not new_project_name), rval)

        if triggered & {'select-load-snapshot', 'input-snapshot-name'}:
            snapshot_nominated = select_snapshot is not None
            new_snapshot_name = input_snapshot_name is not None and input_snapshot_name != ''
            if 'select-load-snapshot' in triggered:
                _disable_snapshot_load_buttons(not(snapshot_nominated), rval)
            if 'input-snapshot-name' in triggered:
                _disable_snapshot_create_button(not new_snapshot_name, rval)
            _disable_snapshot_rename_button(not(snapshot_nominated and new_snapshot_name), rval)

        return rval

    # -----------------------------------------------------------------------------
    # Event Action Callbacks (Create, Load, Delete, Snapshot)
    # -----------------------------------------------------------------------------
    @app.callback(
        output = dict(
            active_project_id = Output("active-project-id", "data", allow_duplicate = True),
        ),
        # Triggers
        inputs = dict(
            buttons = dict(
                n_clicks = Input({'type': 'action-button-ps', 'key': ALL}, 'n_clicks')
            ),
            delete_project_confirm = Input('delete-project-confirm-dialog', 'submit_n_clicks'),
            delete_snapshot_confirm = Input('delete-snapshot-confirm-dialog', 'submit_n_clicks'),
        ),

        state = dict(
            active_project_id = State('active-project-id', 'data'),
            session_id = State('session-id', 'data'),
            app_state = State('app-state', 'data'),
            input_project_name = State('input-project-name', 'value'),
            input_snapshot_name = State('input-snapshot-name', 'value'),
            select_project = State('select-load-project', 'value'),
            select_snapshot = State('select-load-snapshot', 'value'),
        ),
        prevent_initial_call = True
    )
    def handle_project_actions(
        active_project_id,
        **kwargs 
    ):
        # The buttons fire together, with no clicks, when they are drawn: act on the one clicked
        clicked = callback_utils.get_clicked_trigger()
        if clicked is None:
            raise PreventUpdate

        triggered = cast(dict, clicked.id)

        app_state = kwargs.get('app_state')
        app_state = json.loads(app_state) if app_state else {}

        rval = callback_utils.create_noupdate_return()

        if isinstance(triggered, str):
            match triggered:
                case 'delete-project-confirm-dialog':
                    project_id = kwargs['select_project']
                    if project_id is not None:
                        print (f'Deleting project {project_id}')
                        try:
                            active_project_id = delete_project(
                                app.project_provider,
                                project_id,
                                active_project_id,
                                app_state.get('model_type', 'default')
                            )
                        except Exception as e:
                            logger.exception('Could not delete Project ID: %s;', project_id, exc_info = True)

                        callback_utils.update_property_by_id(
                            'active-project-id',
                            'data',
                            active_project_id,
                            rval
                        )

                case 'delete-snapshot-confirm-dialog':
                    snapshot_id = kwargs['select_snapshot']
                    if snapshot_id is not None:
                        print (f'Deleting snapshot {snapshot_id}')
                        delete_snapshot(
                            app.project_provider,
                            active_project_id,
                            snapshot_id
                        )

                        callback_utils.update_property_by_id(
                            'active-project-id',
                            'data',
                            active_project_id,
                            rval
                        )
                case _:
                    print (f'Unknown trigger: {triggered}')

            return rval

        match triggered['key']:

            case 'rename-project':
                new_name = kwargs['input_project_name']
                if new_name is not None:
                    rename_project(
                        app.project_provider,
                        active_project_id,
                        new_name.strip()
                    )
                    callback_utils.update_property_by_id(
                        'active-project-id',
                        'data',
                        active_project_id,
                        rval
                    )

            case 'create-snapshot':
                snapshot_name = kwargs['input_snapshot_name']
                if snapshot_name is not None:
                    s_id = create_snapshot(
                        app.project_provider,
                        active_project_id,
                        snapshot_name.strip()
                    )
                    callback_utils.update_property_by_id(
                        'active-project-id',
                        'data',
                        active_project_id,
                        rval
                    )

            case 'load-project':
                project_id = kwargs['select_project']
                if project_id is not None:
                    can_load = verify_project_exists(
                        app.project_provider, project_id
                    )
                    if can_load:
                        if kwargs['session_id']:
                            app.project_provider.set_session_project_id(
                                kwargs['session_id'],
                                project_id
                            )

                        callback_utils.update_property_by_id(
                            'active-project-id',
                            'data',
                            project_id,
                            rval
                        )


            case 'load-snapshot':
                snapshot_id = kwargs['select_snapshot']
                if snapshot_id is not None:
                    created_project_id = load_snapshot(
                        app.project_provider,
                        active_project_id,
                        snapshot_id
                    )
                    if created_project_id is not None:
                        if kwargs['session_id']:
                            app.project_provider.set_session_project_id(
                                kwargs['session_id'],
                                created_project_id
                            )

                        callback_utils.update_property_by_id(
                            'active-project-id',
                            'data',
                            created_project_id,
                            rval
                        )

            case 'new-project':
                model_type = app_state.get('model_type', 'default')
                created_project_id = new_project(
                    app.project_provider,
                    model_type
                )
                if created_project_id is not None:
                    if kwargs['session_id']:
                        app.project_provider.set_session_project_id(
                            kwargs['session_id'],
                            created_project_id
                        )

                    callback_utils.update_property_by_id(
                        'active-project-id',
                        'data',
                        created_project_id,
                        rval
                    )
                
            case 'duplicate-project':
                created_project_id = duplicate_project(
                    app.project_provider,
                    active_project_id
                )
                if created_project_id is not None:
                    if kwargs['session_id']:
                        app.project_provider.set_session_project_id(
                            kwargs['session_id'],
                            created_project_id
                        )

                    callback_utils.update_property_by_id(
                        'active-project-id',
                        'data',
                        created_project_id,
                        rval
                    )

            case 'delete-project':
                # Launches confirm via another callback.
                pass

            case 'rename-snapshot':
                new_name = kwargs['input_snapshot_name']
                snapshot_id = kwargs['select_snapshot']
                if new_name is not None and snapshot_id is not None:
                    rename_snapshot(app.project_provider, snapshot_id, new_name)

                callback_utils.update_property_by_id(
                    'active-project-id',
                    'data',
                    active_project_id,
                    rval
                )

            case 'delete-snapshot':
                # Launches confirm via another callback.
                pass

            case _:
                logger.exception('Unknown trigger when handling project selector action button clicks: %s', triggered)
        
        return rval

    @app.callback(
        Output("delete-project-confirm-dialog", "displayed"),
        Input({'type': 'action-button-ps', 'key': 'delete-project'}, 'n_clicks'),
        prevent_initial_call=True,
    )
    def display_delete_project_confirm(n_clicks):
        if n_clicks:
            return True
        return False

    @app.callback(
        Output("delete-snapshot-confirm-dialog", "displayed"),
        Input({'type': 'action-button-ps', 'key': 'delete-snapshot'}, 'n_clicks'),
        prevent_initial_call=True,
    )
    def display_delete_snapshot_confirm(n_clicks):
        if n_clicks:
            return True
        return False
    