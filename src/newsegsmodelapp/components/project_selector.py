import json
from typing import cast

from dash import Dash, Input, Output, State, ctx, dcc, html, no_update
import dash_bootstrap_components as dbc
from dash_iconify import DashIconify
import sqlalchemy as sa

from newsegsmodelapp.backend import db
from newsegsmodelapp.backend.db import db_tables as tbls
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface


# -----------------------------------------------------------------------------
# Helper Database Query Functions
# -----------------------------------------------------------------------------
def get_all_projects():
    engine = db.get_engine()
    with engine.connect() as conn:
        stmt = sa.select(tbls.projects.c.id, tbls.projects.c.label)
        return conn.execute(stmt).fetchall()

def get_snapshots_for_project(project_id):
    if not project_id:
        return []
    engine = db.get_engine()
    with engine.connect() as conn:
        stmt = sa.select(tbls.snapshots.c.snapshot_id, tbls.snapshots.c.label).where(tbls.snapshots.c.project_id == project_id)
        return conn.execute(stmt).fetchall()

def delete_project_by_id(project_id: int):
    engine = db.get_engine()
    with engine.begin() as conn:
        conn.execute(tbls.snapshots.delete().where(tbls.snapshots.c.project_id == project_id))
        conn.execute(tbls.projects.delete().where(tbls.projects.c.project_id == project_id))

def create_snapshot(project_id: int, label: str) -> int:
    engine = db.get_engine()
    with engine.begin() as conn:
        res = conn.execute(tbls.snapshots.insert().values(project_id=project_id, label=label))
        return res.inserted_primary_key[0]

# -----------------------------------------------
# Helper functions
# -----------------------------------------------

def fetch_project_options(
        project_provider: NewsegsProjectProviderInterface,
        model_type: str|None = None
    ) -> list[dict[str, str]]:
    """Obtains available projects"""
    all_projects = project_provider.list_projects(model_type = model_type).to_dict(orient = 'list')
    if not all_projects:
        return []
    return [
        {
            'value' : str(all_projects['id'][i]),
            'label': f'{all_projects['label'][i]} [{all_projects['created_at'][i]}]'
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
            'label': f'{all_snapshots['label'][i]} [{all_snapshots['created_at'][i]}]'
        }
        for i in range(len(all_snapshots['snapshot_id']))
    ]

def create_project(
    project_provider: NewsegsProjectProviderInterface,
    current_project_id: str,
    new_project_label: str,
    model_type: str | None = None
) -> NewsegsProject:
    if current_project_id:
        new_proj = cast(NewsegsProject, project_provider.duplicate_component(current_project_id))
    else:
        current_project_id = project_provider.get_session_project_id(model_type = model_type, on_missing = 'last')
        new_proj = cast(NewsegsProject, project_provider.duplicate_component(current_project_id))
    new_proj.name = new_project_label
    new_proj.revision += 1
    project_provider.upsert_component(new_proj)
    return new_proj

def delete_project(
    project_provider: NewsegsProjectProviderInterface,
    project_id: str,
):
    returned = project_provider.delete_component(project_id)
    if returned:
        raise ValueError('Project could not be deleted')
    
def insert_new_project(label: str | None = None) -> int:
    """Inserts a new project into the database and returns its project_id"""
    global results
    results.append({'project_id': len(results), 'label': label})
    return results[-1].get('project_id')
    engine = db.get_engine()
    with engine.begin() as conn:
        result = conn.execute(
            tbls.projects.insert().values(
                label = label if label else sa.null,
                retain = False
            )
        )
    if result is None or result.inserted_primary_key is None:
        raise ValueError(f'Project not inserted: {label}')
    return result.inserted_primary_key[0]

# -----------------------------------------------
# Layout component
# -----------------------------------------------
def create_project_selector():
    return dbc.Container(
        [
            dcc.Store(id="active-snapshot-id", storage_type="session"),

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

            dbc.Card(
                dbc.CardBody(
                    [
                        # 1. Main Row (always visible)
                        dbc.Row(
                            [
                                dbc.Col([
                                    dbc.Label(html.H4('Project'), class_name = 'fw-bold'), # pyright: ignore[reportCallIssue]
                                    dcc.Input(
                                        id = 'project-label-input',
                                        type = 'text',
                                        placeholder = 'Select or enter project name',
                                        list = 'project-datalist-options',
                                        className = 'fw-bold'
                                    ),
                                    html.Datalist(id = 'project-datalist-options')
                                ],
                                md = 6,
                                class_name = 'align-middle',
                                #width = True
                                ), # pyright: ignore[reportCallIssue]
                                dbc.Col(
                                    [
                                        # Save Button (Visible/Enabled when label is unused an non-empty)
                                        dbc.Button(
                                            [DashIconify(icon = 'bi:floppy-fill', className = 'me-1'), 'Save New'],
                                            id = 'btn-save-project',
                                            color = 'primary',
                                            disabled = True,
                                            style = {'display': 'none'},
                                        ), # pyright: ignore[reportCallIssue]
                                        # Load Button (Visible/Enabled when label matches another existing project)
                                        dbc.Button(
                                            [DashIconify(icon = 'bi:box-arrow-in-right', className = 'me-1'), 'Load'],
                                            id = 'btn-load-project',
                                            color = 'primary',
                                            disabled = True,
                                            style = {'display': 'none'},
                                        ), # pyright: ignore[reportCallIssue]
                                    ],
                                    width = 'auto',
                                    class_name = 'd-flex align-items-end gap-2',
                                ), # pyright: ignore[reportCallIssue]
                                dbc.Col(
                                    [
                                        # Details Collapsible / Accordion
                                        dbc.Accordion(
                                            [
                                                dbc.AccordionItem(
                                                    title = html.H4('Snapshots'),
                                                    children = [
                                                        # Snapshot management row
                                                        dbc.Row(
                                                            [
                                                                dbc.Col(
                                                                    [
                                                                        dbc.Label('Snapshot', class_name = 'fw-bold mb-1'), # pyright: ignore[reportCallIssue]
                                                                        dbc.Input(
                                                                            id = 'snapshot-label-input',
                                                                            type = 'text',
                                                                            placeholder = 'Leave blank for datetime',
                                                                            value = '',
                                                                            list = 'snapshot-datalist-options',
                                                                        ), # pyright: ignore[reportCallIssue]
                                                                        html.Datalist(id = 'snapshot-datalist-options'),
                                                                    ],
                                                                    width = True,
                                                                ), # pyright: ignore[reportCallIssue]
                                                                dbc.Col(
                                                                    [
                                                                        # Save snapshot (Disabled if snapshot label exists)
                                                                        dbc.Button(
                                                                            [DashIconify(icon = 'bi:camera-fill', className = 'me-1'), 'Save Snapshot'],
                                                                            id = 'btn-save-snapshot',
                                                                            color = 'secondary',
                                                                            size = 'sm',
                                                                            disabled = False,
                                                                        ), # pyright: ignore[reportCallIssue]
                                                                        # Load snapshot (Enabled only if snapshot label exists)
                                                                        dbc.Button(
                                                                            [DashIconify(icon = 'bi:download', className = 'me-1'), 'Load Snapshot'],
                                                                            id = 'btn-load-snapshot',
                                                                            color = 'secondary',
                                                                            size = 'sm',
                                                                            disabled = True,
                                                                        ), # pyright: ignore[reportCallIssue]
                                                                        # Load snapshot (Enabled only if snapshot label exists)
                                                                        dbc.Button(
                                                                            [DashIconify(icon = 'bi:trash-fill', className = 'me-1'), 'Delete Snapshot'],
                                                                            id = 'btn-delete-snapshot',
                                                                            color = 'danger',
                                                                            size = 'sm',
                                                                            disabled = True,
                                                                        ), # pyright: ignore[reportCallIssue]
                                                                    ],
                                                                    width = 'auto',
                                                                    class_name = 'd-flex align-items-end gap-2',
                                                                ), # pyright: ignore[reportCallIssue]
                                                            ],
                                                            class_name = 'align-items-center border-bottom mb-2 pb-2',
                                                        ), # pyright: ignore[reportCallIssue]
                                                        
                                                        # Project action row
                                                        dbc.Row(
                                                            [
                                                                dbc.Col(
                                                                    dbc.Button(
                                                                        [DashIconify(icon='bi:trash-fill', className = 'me-1'), 'Delete Current Project'],
                                                                        id = 'btn-delete-project',
                                                                        color = 'danger',
                                                                        outline = True,
                                                                        size = 'sm'
                                                                    ), # pyright: ignore[reportCallIssue]
                                                                    width = 'auto',
                                                                ) # pyright: ignore[reportCallIssue]
                                                            ],
                                                             
                                                        ), # pyright: ignore[reportCallIssue]
                                                    ],
                                                    class_name = 'p-0 m-0',
                                                ), # pyright: ignore[reportCallIssue]
                                            ],
                                            start_collapsed = True,
                                            flush = True,
                                        ), # pyright: ignore[reportCallIssue]
                                    ]
                                )
                            ],
                            className = 'align-items-center mb-2'
                        ), # pyright: ignore[reportCallIssue]

                        
                    ],
                    class_name = 'p-1 m-0'
                ), # pyright: ignore[reportCallIssue]
                class_name = 'border-0 p-1 m-0'
            ), # pyright: ignore[reportCallIssue]
        ],
        fluid = True,
        class_name = 'p-0',
    ) # pyright: ignore[reportCallIssue]

def create_project_selector_block(**kwargs):
    return html.Div(
        create_project_selector()
    )

# -----------------------------------------------
# Callbacks
# -----------------------------------------------
def add_project_selector_callbacks(app: NewsegsDash) -> NewsegsDash:

    @app.callback(
        Output('project-datalist-options', 'children'),
        Output("snapshot-datalist-options", "children"),
        Output('project-label-input', 'value'),

        # Project Buttons logic
        Output("btn-save-project", "style"),
        Output("btn-save-project", "disabled"),
        Output("btn-load-project", "style"),
        Output("btn-load-project", "disabled"),
        Output("btn-delete-project", "disabled"),

        # Snapshot Buttons logic
        Output("btn-save-snapshot", "disabled"),
        Output("btn-load-snapshot", "disabled"),

        # State Inputs
        Input('active-project-id', 'data'),
        Input('project-label-input', 'value'),
        Input('snapshot-label-input', 'value'),
        Input('app-state', 'data'),
    )
    def update_ui_states(
        active_project_id,
        current_project_label,
        current_snapshot_label,
        app_state,
    ):
        app_state = json.loads(app_state) if app_state else {}
        model_type = app_state.get('selected_model', 'default')

        # 1. Fetch Projects & Populate Datalist
        all_projects = fetch_project_options(app.project_provider, model_type)

        project_map = {row['label']: row['value'] for row in all_projects if row.get('label')}
        project_options = [
            html.Option(value = x['label'], id = x['value']) for x in all_projects
        ]

        # Resolve active project label
        active_project_label = next((p['label'] for p in all_projects if p['value'] == active_project_id), "")

        # Sync input value if initialized from active-project store
        input_text = current_project_label if current_project_label is not None else active_project_label

        # 2. Compute Save/Load state for Project
        has_text = bool(input_text and input_text.strip())
        is_existing = input_text in project_map
        is_active = (active_project_id is not None) and (project_map.get(input_text) == active_project_id)

        # Save button: Visible and enabled only if label is non-empty and unused
        show_save = has_text and not is_existing
        save_style = {"display": "inline-block"} if show_save else {"display": "none"}
        save_disabled = not show_save

        # Load button: Visible and enabled only if label is used and doesn't match active project
        show_load = is_existing and not is_active
        load_style = {"display": "inline-block"} if show_load else {"display": "none"}
        load_disabled = not show_load

        # Delete button: Disabled if no project active
        delete_disabled = active_project_id is None

        # 3. Fetch Snapshots for active project
        if active_project_id:
            all_snapshots = fetch_snapshot_options(
                app.project_provider,
                active_project_id
            )
        else:
            all_snapshots = []
        snapshot_labels = {x['label'] for x in all_snapshots}
        snapshot_options = [
            html.Option(
                value = x['label'],
                id = x['value']
            ) 
            for x in all_snapshots
        ]

        # 4. Compute Save/Load state for Snapshot
        snap_text_valid = bool(current_snapshot_label and current_snapshot_label.strip())
        snap_exists = current_snapshot_label in snapshot_labels

        save_snap_disabled = (not snap_text_valid) or snap_exists
        load_snap_disabled = not snap_exists

        return (
            project_options,
            snapshot_options,
            input_text,
            save_style,
            save_disabled,
            load_style,
            load_disabled,
            delete_disabled,
            save_snap_disabled,
            load_snap_disabled,
        )

    # -----------------------------------------------------------------------------
    # Event Action Callbacks (Create, Load, Delete, Snapshot)
    # -----------------------------------------------------------------------------

    @app.callback(
        Output("active-project-id", "data"),
        Output("active-snapshot-id", "data"),

        # Triggers
        Input("btn-save-project", "n_clicks"),
        Input("btn-load-project", "n_clicks"),
        Input("delete-confirm-dialog", "submit_n_clicks"),
        Input("btn-save-snapshot", "n_clicks"),
        Input("btn-load-snapshot", "n_clicks"),

        # States
        State("project-label-input", "value"),
        State("snapshot-label-input", "value"),
        State("active-project-id", "data"),
        State('app-state', 'data'),

        prevent_initial_call=True,
    )
    def handle_project_actions(
        save_proj_click, load_proj_click, confirm_delete_click,
        save_snap_click, load_snap_click,
        project_label, snapshot_label, active_project_id, app_state
    ):
        triggered = ctx.triggered_id

        # Save Project
        if triggered == "btn-save-project" and project_label:
            new_proj = create_project(
                app.project_provider,
                active_project_id,
                project_label.strip())
            return new_proj.id, None

        # Load Project
        if triggered == "btn-load-project" and project_label:
            app_state = json.loads(app_state) if app_state else {}
            model_type = app_state.get('selected_model', 'default')
            all_projects = fetch_project_options(
                app.project_provider,
                model_type
            )
            matched_id = next((p['value'] for p in all_projects if p['label'] == project_label), None)
            if matched_id:
                return matched_id, None
            return no_update, no_update

        # Delete Project
        if triggered == "delete-confirm-dialog" and active_project_id:
            delete_project_by_id(active_project_id)
            return None, None

        # Create Snapshot
        if triggered == "btn-save-snapshot" and current_active_proj and snapshot_label:
            snap_id = create_snapshot(current_active_proj, snapshot_label.strip())
            return current_active_proj, snap_id

        # Load Snapshot
        if triggered == "btn-load-snapshot" and current_active_proj and snapshot_label:
            snaps = get_snapshots_for_project(current_active_proj)
            snap_id = next((s.snapshot_id for s in snaps if s.label == snapshot_label), None)
            return current_active_proj, snap_id

        return current_active_proj, None


    # @app.callback(
    #     Output("delete-confirm-dialog", "displayed"),
    #     Input("btn-delete-project", "n_clicks"),
    #     prevent_initial_call=True,
    # )
    # def display_delete_confirm(n_clicks):
    #     if n_clicks:
    #         return True
    #     return False


    # @app.callback(
    #     Output("project-input", "value"),
    #     Input("active-project", "data"),
    #     State("project-datalist-options", "children")
    # )
    # def sync_active_project_to_ui(active_data, options):
    #     """Initializes input label when active-project changes."""
    #     if not active_data or not options:
    #         return ""
        
    #     # Match active_data (project_id) with corresponding option label
    #     for opt in options:
    #         if opt.get("props", {}).get("id", {}).get('key') == str(active_data):
    #             return opt.get("props", {}).get("value")
    #     return ""
    
    # @app.callback(
    #     Output("active-project", "data"),
    #     Output("project-datalist-options", "children"),
    #     Input("save-project-btn", "n_clicks"),
    #     State("project-input", "value"),
    #     State("project-datalist-options", "children"),
    #     prevent_initial_call=True
    # )
    # def handle_project_selection_and_creation(n_clicks, typed_value, options):
    #     """Saves typed text as a new SQLite row or matches existing project label."""
    #     if not typed_value:
    #         return None, options

    #     # Check if typed text matches an existing project label
    #     existing_map = {
    #         opt["props"]["value"]: opt["props"]["id"] 
    #         for opt in options if "props" in opt
    #     }

    #     if typed_value in existing_map:
    #         return int(existing_map[typed_value]), options

    #     # Create new project in SQLite if label doesn't exist
    #     new_id = insert_new_project(label=typed_value)

    #     updated_options = list(options)
    #     updated_options.append(html.Option(value=typed_value, id=str(new_id)))

    #     return new_id, updated_options

    return app