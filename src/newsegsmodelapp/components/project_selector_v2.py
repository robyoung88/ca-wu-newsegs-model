
import json
from typing import Any

import dash
from dash import ALL, Input, Output, State, dcc, html, ctx
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from newsegsmodelapp.components import callback_utils
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface

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
        for i in range(len(all_projects['id']))
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

# -----------------------------------------------
# Layout component
# -----------------------------------------------
def create_project_selector(**kwargs):
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
                        placeholder="Project Name",
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
                        placeholder="Snapshot Name",
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
                        placeholder="Select existing project...",
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
                        placeholder="Select snapshot...",
                        size="sm",
                    ),
                    dbc.Button(
                        [DashIconify(icon="bi:box-arrow-in-right", className="me-1"), "Load"],
                        id = {'type': 'action-button-ps', 'key': 'load-snapshot'},
                        #id="btn-load-snapshot",
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
                            #id="btn-new-project",
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
                            #id="btn-duplicate-project",
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
                            #id="btn-delete-project",
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
                            #id="btn-delete-snapshot",
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

def add_project_selector_callbacks(app: NewsegsDash):
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
        callback_utils.update_return_by_id(
            {'type': 'action-button-ps', 'key': 'load-project'},
            'disabled',
            state,
            rval
        )
        callback_utils.update_return_by_id(
            {'type': 'action-button-ps', 'key': 'delete-project'},
            'disabled',
            state,
            rval
        )

    def _disable_project_rename_button(state: bool, rval):
        callback_utils.update_return_by_id(
                {'type': 'action-button-ps', 'key': 'rename-project'},
                'disabled',
                state,
                rval
            )

    def _disable_snapshot_load_buttons(state: bool, rval):
        callback_utils.update_return_by_id(
            {'type': 'action-button-ps', 'key': 'load-snapshot'},
            'disabled',
            state,
            rval
        )
        callback_utils.update_return_by_id(
            {'type': 'action-button-ps', 'key': 'rename-snapshot'},
            'disabled',
            state,
            rval
        )
        callback_utils.update_return_by_id(
            {'type': 'action-button-ps', 'key': 'delete-snapshot'},
            'disabled',
            state,
            rval
        )

    def _disable_snapshot_create_button(state: bool, rval):
        callback_utils.update_return_by_id(
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

        triggered_id = ctx.triggered_id
        if isinstance(triggered_id, str) and triggered_id == 'active-project-id':
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
            
        if isinstance(triggered_id, str) and triggered_id in set(('active-project-id', 'app-state')):
            # Update project selector
            app_state = json.loads(app_state) if app_state else {}
            model_type = app_state.get('selected_model', 'default')
            all_projects = fetch_project_options(app.project_provider, model_type)
            rval['project_select']['options'] = all_projects
            rval['project_select']['value'] = None

            # As no project selected, disable the load and delete buttons
            _disable_project_load_buttons(True, rval)

            # Also clear the name input
            rval['input_project_name']['value'] = None
            _disable_project_rename_button(True, rval)

        if isinstance(triggered_id, str):
            match triggered_id:
                case 'select-load-project':
                    project_nominated = select_project is not None
                    _disable_project_load_buttons(not(project_nominated), rval)

                case 'select-load-snapshot':
                    snapshot_nominated = select_snapshot is not None
                    _disable_snapshot_load_buttons(not(snapshot_nominated), rval)

                case 'input-project-name':
                    new_project_name = input_project_name
                    _disable_project_rename_button((new_project_name is None or not new_project_name), rval)

                case 'input-snapshot-name':
                    new_snapshot_name = input_snapshot_name
                    _disable_snapshot_create_button((new_snapshot_name is None or not new_snapshot_name), rval)

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
            )
        ),

        state = dict(
            active_project_id = State('active_project_id', 'data')
        ),
        prevent_initial_call = True
    )
    def handle_project_actions(
        active_project_id,
        **kwargs 
    ):
        triggered = ctx.triggered_id
        trig_val = callback_utils.get_triggered_value()
        if not trig_val:
            raise PreventUpdate
        
        raise PreventUpdate

    @app.callback(
        Output({'type': 'action-button-ps', 'key': ALL}, 'style'),
        Input({'type': 'action-button-ps', 'key': ALL}, 'n_clicks'),
        prevent_initial_call = True
    )
    def single_output_list(n_clicks):
        context = ctx
        outputs = ctx.outputs_grouping
        olist = ctx.outputs_list

        rval = callback_utils.create_noupdate_return()
        return rval

    @app.callback(
        Output({'type': 'action-button-nonexistent', 'key': ALL}, 'style'),
        Input({'type': 'action-button-ps', 'key': ALL}, 'n_clicks'),
        prevent_initial_call = True
    )
    def single_output_missing(n_clicks):
        context = ctx
        outputs = ctx.outputs_grouping
        olist = ctx.outputs_list

        rval = callback_utils.create_noupdate_return()
        return rval
        
        raise PreventUpdate