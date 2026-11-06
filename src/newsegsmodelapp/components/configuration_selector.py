"""The configuration selector: choosing, adding, duplicating, removing, uploading and downloading the configurations (metamodels) of a project.
"""
import logging
logger = logging.getLogger(__name__)

import base64
import json
from typing import Any, Sequence, cast

from dash import ALL, Input, Output, State, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate
import pathvalidate

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.components import export
from newsegsmodelapp.components.export import metamodel_to_config_file
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelapp.components import icons
from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.newsegsmetamodel.lightweightnewsegsmetamodel import LightweightNewsegsMetaModel
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.util import jsonfuncs, naming
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

# -----------------------------------------------
# Layout
# -----------------------------------------------

def create_config_selector_headerbutton(
    config_index: int = 0,
    metamodel: LightweightNewsegsMetaModel | None = None,
    is_focussed: bool | None = None,
):
    """Create the button which focusses a configuration (metamodel) in the page header.

    Outlined unless the configuration is the focussed one.

    Args:
        config_index: Index of the configuration (metamodel) within the project.
        metamodel: The lightweight metamodel.
        is_focussed: Whether the configuration is the focussed metamodel.

    Returns:
        The button.
    """
    if is_focussed:
        do_outline = False
    else:
        do_outline = True
    
    contents = dbc.Button(
        html.I(
            className = icons.get_icon('config-{}'.format(config_index+1), style_name = 'raw'),
            style={'display': 'inline'}
        ),
        color='primary',
        id = {'type': 'config-hdrfocus-btn', 'index': config_index},
        outline = do_outline,
        title = metamodel.name if metamodel else '',
    )

    return contents

def create_header_metamodel_input_container(supersection: str) -> html.Div:
    """Create the container of the configuration buttons of the page header.

    Args:
        supersection: The supersection of the container.

    Returns:
        The container.
    """
    return html.Div(
        [
            dbc.Button(
                html.I(
                    className = icons.get_icon('config-1', style_name = 'raw'),
                    style={'display': 'inline'}
                ),
                color='primary',
                id = {'type': 'config-hdrfocus-btn', 'index': 0},
                outline = False
            )
        ],
        id = {
            'type': 'metamodel-input-container', 'purpose': 'container',
            'supersection': supersection, 'section': 'configuration-header-selector',
            'key': 'results-header-metamodel-input-container', 'subindex': 0
            },
        className = 'configuration-selector-hdrcontainer'
    )

CONFIGURATION_NAME_HINT = 'Configuration name, e.g. Heat pumps and PV'
"""The hint in the name box of a configuration with no name."""

CONFIGURATION_NAME_FOCUS_ID = 'configuration-name-focus'
"""Store of the index of the configuration whose name box takes the focus, after a duplicate, or `None`."""

def create_single_configuration_selector_row(
    config_index: int = 0,
    metamodel: LightweightNewsegsMetaModel | None = None,
    is_focussed: bool | None = None,
    reference_size: int = 20,
):
    
    """Create the row of the configuration selector for one configuration (metamodel).

    The first configuration cannot be removed.

    Args:
        config_index: Index of the configuration (metamodel) within the project.
        metamodel: The lightweight metamodel.
        is_focussed: Whether the configuration is the focussed metamodel.
        reference_size: Size of the icons.

    Returns:
        The row.
    """
    if config_index < 1:
        primary_container = html.H1
        show_remove = False
    else:
        primary_container = html.H2
        show_remove = True
    
    contents: list[Any] = [icons.get_icon(
        'config-'+str(config_index+1), 
        icon_class = icons.ICON_COLOUR_CLASSES[config_index % len(icons.ICON_COLOUR_CLASSES)]
    ),]
    
    config_name = metamodel.name if metamodel is not None else ''

    is_focussed = True if is_focussed is None else is_focussed
    
    # An unnamed configuration shows the hint, at a size to fit it
    contents.append(
        dcc.Input(
            value = config_name,
            placeholder = CONFIGURATION_NAME_HINT,
            debounce = True,
            type = 'text',
            id = {'type': 'config-name-input', 'index': config_index},
            size = str(reference_size * 1.3 if config_name else len(CONFIGURATION_NAME_HINT)),
            className = 'configuration-selector-row-name-input'
        )
    )

    button_container_children = []
    
    button_container_children += [
        dbc.Button(
            html.I(
                className = icons.get_icon('config-focus', style_name = 'raw'),
                style={'display': 'inline'}
            ),
            color = 'primary',
            id = {'type': 'config-focus-btn', 'index': config_index},
            outline = not(is_focussed),
            title = 'Focus configuration',
        ),

        dbc.Button(
            html.I(
                className = icons.get_icon('config-duplicate', style_name = 'raw'),
                style={'display': 'inline'}
            ),
            color="primary",
            id = {'type': 'config-dup-btn', 'index': config_index},
            outline = True,
            title = 'Duplicate configuration'
        ),

        dbc.Button(
            html.I(
                className = icons.get_icon('config-download', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
            color='secondary',
            id = {'type': 'config-download-btn', 'index': config_index},
            outline = True,
            title = 'Download configuration as json'
        ),
        
        dcc.Upload(
            dbc.Button(
                html.I(
                    className = icons.get_icon('config-upload', style_name = 'raw'),
                    style = {'display': 'inline'}
                ),
                color='secondary',
                id = {'type': 'config-upload-btn', 'index': config_index},
                outline = True,
                title = 'Overwrite configuration with uploaded json',
            ),
            id = {'type': 'config-upload', 'index': config_index},
            multiple = False,
            enable_folder_selection = False,
            accept = '.json',
            className = 'upload-button'
        ),
            
        dbc.Button(
            html.I(
                className = icons.get_icon('results-download', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
            color='secondary',
            id = {'type': 'results-predownload-btn', 'page': 'model_configuration', 'key':  f'config-{config_index+1}'},
            outline = True,
            title = 'Download results as spreadsheet'
        ),
    ]

    if show_remove:
        button_container_children.append(
            dbc.Button(
                html.I(
                    className = icons.get_icon('config-remove', style_name = 'raw'),
                    style={'display': 'inline'}
                ),
                color="primary",
                id={'type': 'config-remove-btn', 'index': config_index},
                outline=True,
            )
        )
    
    button_container = html.Div(
        button_container_children,
        className = 'configuration-selector-row-button-container'
    )

    contents.append(button_container)
    
    return (
        dbc.Row([
            dbc.Col([
                primary_container(
                    contents
                )
            ])
        ],
        id={'type':'comparator-conf-row', 'index': config_index},
        class_name = 'configuration-selector-row'
        )
    )

def create_configuration_selector():
    """Create the configuration selector: the rows of the configurations of the project, and the download of their JSON.

    Returns:
        The layout.
    """
    return html.Div([
        
        html.Div(
            [],
            id = {'type': 'metamodel-input-container', 'supersection': 'configurations', 'section': 'configuration-selector'}
        ),
        dcc.Download(id='download-config-json'),
        dcc.Store(id = CONFIGURATION_NAME_FOCUS_ID, data = None, storage_type = 'memory'),
    ])

# -----------------------------------------------
# Callbacks
# -----------------------------------------------

def _create_configuration_rows_for_metamodels(
    metamodels: Sequence[LightweightNewsegsMetaModel],
    focussed_index: int = 0,
):
    contents = [
        create_single_configuration_selector_row(
            i, mm, i == focussed_index
        ) for i, mm in enumerate(metamodels)
    ]
    return contents

def _create_configuration_header_elements_for_metamodels(
    metamodels: Sequence[LightweightNewsegsMetaModel],
    focussed_index: int = 0,
):
    contents = [
        create_config_selector_headerbutton(
            i, mm, i == focussed_index
        ) for i, mm in enumerate(metamodels)
    ]
    return contents

def add_configuration_selector_callbacks(app: NewsegsDash):
    # Populate
    """Bind the callbacks of the configuration selector: showing, focussing, adding, duplicating, removing, uploading and downloading configurations.

    Args:
        app: The Dash app.
    """
    @app.callback(
        Output({'type': 'metamodel-input-container', 'supersection': ALL, 'section': 'configuration-selector'}, 'children'),
        Output({
            'type': 'metamodel-input-container', 'purpose': 'container',
            'supersection': ALL, 'section': 'configuration-header-selector',
            'key': ALL, 'subindex': ALL
        }, 'children'),

        Input('active-project-id', 'data'),
        State({'type': 'metamodel-input-container', 'supersection': ALL, 'section': 'configuration-selector'}, 'id'),
        State({
            'type': 'metamodel-input-container', 'purpose': 'container',
            'supersection': ALL, 'section': 'configuration-header-selector',
            'key': ALL, 'subindex': ALL
        }, 'id'),
    )
    def population_configuration_selector(
        active_project_id,
        configuration_container_ids,
        configuration_header_ids,
    ):
        if (
            active_project_id is None 
            or (
                len(configuration_container_ids) == 0
                and len(configuration_header_ids) == 0
            )
        ):
            raise PreventUpdate

        provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)
        logger.debug('Getting lightweight project - Populating configuration selector')
        lproj = provider.get_lightweight_project(active_project_id)
        config_rows = _create_configuration_rows_for_metamodels(lproj.metamodels, lproj.focussed_metamodel_index)
        header_elements = _create_configuration_header_elements_for_metamodels(lproj.metamodels, lproj.focussed_metamodel_index)

        logger.debug(
            "Created configuration selector elements for project %s. "
            "Number of metamodels: %d; Focussed metamodel index: %d;",
            lproj.id, len(lproj.metamodels), lproj.focussed_metamodel_index
        )

        return (
            [config_rows] * len(configuration_container_ids),
            [header_elements] * len(configuration_header_ids)
        )

    # Rename
    @app.callback(
        Output('active-project-id', 'data', allow_duplicate = True),

        Input({'type': 'config-name-input', 'index': ALL}, 'value'),

        State('active-project-id', 'data'),
        prevent_initial_call = True
    )
    def rename_config(config_names, active_project_id):
        trig = ctx.triggered_id
        if trig is None or len(ctx.triggered) > 1:
            raise PreventUpdate

        provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)
        logger.debug('Getting lightweight project - Renaming metamodel')
        lproj = provider.get_lightweight_project(active_project_id)

        mm_index = trig['index']
        new_name = callback_utils.get_triggered_value()

        mm = lproj.metamodels[mm_index]
        if not mm or mm.name == new_name:
            raise PreventUpdate
        if not (new_name or '').strip():
            # A configuration keeps its name: redraw the selector to show it again
            return active_project_id

        old_name = mm.name

        # By changing the metadata, the MM should pick up the new name next time it is
        # taken from the store as the revision will by incremented by default
        # Give the project ID to invalidate cache
        provider.metamodel_provider.set_component_metadata(mm.id, 'label', new_name, project_id = active_project_id)

        logger.info(
            'Renamed metamodel %s; Old name: %s; New name: %s;',
            mm.id, old_name, new_name
        )
        
        # However, for this to be picked up by the front end, we will have to invalidate the project provider cache
        provider.invalidate_cache_for_component(lproj.id)

        # Trigger a rebuild of the page in case the name is baked into e.g. button titles.
        return active_project_id

    # Duplicate
    @app.callback(
        Output('active-project-id', 'data', allow_duplicate = True),
        Output(CONFIGURATION_NAME_FOCUS_ID, 'data', allow_duplicate = True),

        Input({'type': 'config-dup-btn', 'index': ALL}, 'n_clicks'),

        State('active-project-id', 'data'),
        prevent_initial_call = True
    )
    def add_duplicate_config(
        n_clicks,
        active_project_id
    ):
        trig = ctx.triggered_id
        if trig is None or len(ctx.triggered) > 1 or not callback_utils.get_triggered_value():
            raise PreventUpdate

        mm_index = trig['index']

        proj = app.project_provider.get_project(active_project_id)
        ref_mm = proj.metamodels[mm_index]

        new_mm = cast(
            NewsegsMetaModel,
            app.project_provider.metamodel_provider.duplicate_component(ref_mm.id) # pyright: ignore[reportAttributeAccessIssue]
        )
        new_mm.name = naming.copy_name(ref_mm.name, (x.name for x in proj.metamodels))

        # Ensure that the variables can be obtained from the project,
        # though they will be identical to the sourced metamodel
        # and so won't add any new variables to the project when the metamodel
        # is appended.
        new_mm.reattach_variables(proj)
        proj.metamodels.append(new_mm) # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]
        
        proj.set_focussed_metamodel(new_mm.id)

        logger.info(
            'Duplicated metamodel %s -> %s; Name: %s; Project revision = %d',
            ref_mm.id, new_mm.id, new_mm.name, proj.revision
        )
        
        app.project_provider.upsert_component(proj)
        # As a change of name does not dirty the metamodel, need to update that
        app.project_provider.metamodel_provider.set_component_metadata(
            new_mm.id, 'label', new_mm.name
        )

        # Trigger interface update, and put the cursor in the copy's name box, so that the user names it
        return active_project_id, len(proj.metamodels) - 1

    # Focus the name box of a copy, with its name selected, as soon as the selector shows it. Waits for the box
    # itself, not for the selector's callback, which Dash may run seconds after the box appears. Redraws soon after
    # can replace the box, so it is focussed again for a few seconds, unless the user has moved on.
    app.clientside_callback(
        """
        function(index) {
            if (index === null || index === undefined) {
                return window.dash_clientside.no_update;
            }
            const id = JSON.stringify({index: index, type: 'config-name-input'});
            const started = Date.now();
            let focussed = null;
            let focussedAt = null;
            const observer = new MutationObserver(() => attempt());
            const stop = () => observer.disconnect();
            function attempt() {
                const input = document.getElementById(id);
                const now = Date.now();
                if (focussed === null && now - started > 20000) {
                    return stop();
                }
                if (focussedAt !== null && now - focussedAt > 3000) {
                    return stop();
                }
                if (!input || input === document.activeElement) {
                    return;
                }
                const active = document.activeElement;
                if (focussed !== null && active && active !== document.body) {
                    return stop(); // The user is elsewhere
                }
                input.focus();
                input.select();
                focussed = input;
                if (focussedAt === null) {
                    focussedAt = now;
                }
            }
            observer.observe(document.body, {childList: true, subtree: true});
            attempt();
            setTimeout(stop, 25000);
            return window.dash_clientside.no_update;
        }
        """,
        Output(CONFIGURATION_NAME_FOCUS_ID, 'data', allow_duplicate = True),
        Input(CONFIGURATION_NAME_FOCUS_ID, 'data'),
        prevent_initial_call = True,
    )

    # Remove
    @app.callback(
        Output('active-project-id', 'data', allow_duplicate = True),

        Input({'type': 'config-remove-btn', 'index': ALL}, 'n_clicks'),

        State('active-project-id', 'data'),
        prevent_initial_call = True
    )
    def remove_config(
        n_clicks,
        active_project_id
    ):
        trig = ctx.triggered_id
        if trig is None or len(ctx.triggered) > 1 or not callback_utils.get_triggered_value():
            raise PreventUpdate

        mm_index = trig['index']


        proj = app.project_provider.get_project(active_project_id)
        if len(proj.metamodels) < 2:
            # Do not delete last metamodel.
            raise PreventUpdate

        mm_to_delete = proj.metamodels.pop(mm_index) # pyright: ignore[reportAttributeAccessIssue]
        app.project_provider.metamodel_provider.delete_component(mm_to_delete.id)
        proj.set_focussed_metamodel_index(proj.get_focussed_metamodel_index())

        logger.info(
            'Deleted metamodel %s from project %s; Project has %d metamodels and the focussed metamodel is %d.',
            mm_to_delete.id, proj.id, len(proj.metamodels), proj.get_focussed_metamodel_index()
        )

        # Should be no need to increment the revision - should occur automatically on pop of the metamodel
        # proj.revision += 1
        app.project_provider.upsert_component(proj)

        # Trigger interface update
        return active_project_id

    # Focus
    @app.callback(
        Output('active-project-id', 'data', allow_duplicate = True),

        Input({'type': 'config-focus-btn', 'index': ALL}, 'n_clicks'),
        Input({'type': 'config-hdrfocus-btn', 'index': ALL}, 'n_clicks'),

        State('active-project-id', 'data'),
        prevent_initial_call = True
    )
    def set_focussed_config(
        n_clicks,
        n_clicks_hdr,
        active_project_id
    ):
        # The buttons fire together, with no clicks, when they are drawn: act on the one clicked
        clicked = callback_utils.get_clicked_trigger()
        if clicked is None or not active_project_id:
            raise PreventUpdate

        mm_index = clicked.id['index'] # pyright: ignore[reportIndexIssue, reportCallIssue, reportArgumentType]
        provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)
        logger.debug('Getting lightweight project - Setting focussed metamodel')
        lproj = provider.get_lightweight_project(active_project_id)

        if lproj.focussed_metamodel_index == mm_index:
            raise PreventUpdate

        old_mm_index = lproj.focussed_metamodel_index
        mm_id = lproj.metamodels[mm_index].id

        provider.set_component_metadata(
            lproj.id, 'focussed_metamodel_id',
            mm_id, increment_revision = False,
        )

        logger.info(
            "Changed focussed metamodel index from %d to %d for project %s.",
            old_mm_index, mm_index, lproj.id
        )

        # Trigger interface update
        # Could be a bit more elegant, but may have to rebuild inputs for some configurations anyway so brute force for now.
        return active_project_id

    # Download metamodel
    @app.callback(
        Output('download-config-json', 'data'),

        Input({'type': 'config-download-btn', 'index': ALL}, 'n_clicks'),

        State('active-project-id', 'data'),

        prevent_initial_call = True
    )
    def download_config_json(n_clicks, active_project_id):
        trig = ctx.triggered_id
        if trig is None or len(ctx.triggered) > 1 or not callback_utils.get_triggered_value():
            raise PreventUpdate

        mm_index = trig['index']
        proj = app.project_provider.get_project(active_project_id)

        mm = proj.metamodels[mm_index]

        odict = metamodel_to_config_file(mm)

        fn = (odict.get('config_name') or 'configuration') + ".json"
        fn = pathvalidate.sanitize_filename(fn)

        logger.info(
            'Downloading metamodel %s to file %s',
            mm.id, fn
        )
        
        return dict(
            content = json.dumps(odict, cls = jsonfuncs.NumpyEncoder, sort_keys=False, indent=4), 
            filename = fn
        )

    # Upload metamodel
    @app.callback(
        Output('active-project-id', 'data', allow_duplicate = True),

        Input({'type': 'config-upload', 'index': ALL}, 'contents'),

        State('active-project-id', 'data'),
        
        prevent_initial_call = True
    )
    def upload_config_json(config_jsons, active_project_id):
        trig = ctx.triggered_id
        if trig is None or len(ctx.triggered) > 1:
            raise PreventUpdate

        trig_val = callback_utils.get_triggered_value()
        if not trig_val:
            raise PreventUpdate

        try:
            working_conf = trig_val
            ctype, cstr = working_conf.split(',')
            cfg = json.loads(base64.b64decode(cstr))
        except json.JSONDecodeError as e:
            logging.exception('Could not decode uploaded metamodel configuration', exc_info = True)
            raise PreventUpdate
        
        mm_config = cfg.get('metamodel')
        if mm_config is None:
            mm_config = cfg
        constr = find_constructor(mm_config['constructor_class'], mm_config['class'])
        if not constr:
            raise PreventUpdate

        mm_new = cast(NewsegsMetaModel, constr(mm_config))
        # Caution: We cannot safely add this new metamodel to the project until we have generated new ids
        # for each component. The variables are given new ids too: with the ids in the file, they would be the
        # variables the file was exported from, so the upload would overwrite their values, and editing it would
        # change the configurations that share them, in this or another project.
        mm_new.anonymise_ids(include_variables = True)

        proj = app.project_provider.get_project(active_project_id)
        mm_new.name = naming.unique_name(mm_new.name, (x.name for x in proj.metamodels))
        proj.metamodels.append(mm_new) # pyright: ignore[reportAttributeAccessIssue]
        proj.set_focussed_metamodel(mm_new.id)
        # Project revision increment should occur on the metamodels.append
        # proj.revision += 1
        app.project_provider.upsert_component(proj)

        logger.info(
            'Added uploaded metamodel to project. Project ID: %s; Metamodel ID: %s; Metamodel name: %s;',
            proj.id, mm_new.id, mm_new.name,
        )

        return active_project_id

    # Download results
    @app.callback(
        output = {
            'modal': {
                'is_opens': Output(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'det-download-confirm'},
                    'is_open'
                )
            },
            'download': {
                'datas': Output(
                    {'type': 'results-download-component', 'page': ALL, 'key': 'det'},
                    'data'
                )
            },
            'toast': {
                'children': Output(
                    {'type': 'result-download-feedback-toast', 'page': ALL, 'key': 'det'},
                    'children'
                ),
                'is_opens': Output(
                    {'type': 'result-download-feedback-toast', 'page': ALL, 'key': 'det'},
                    'is_open'
                ),
            },
            'information': {
                'values': Output(
                    {'type': 'result-download-information', 'page': ALL, 'key': 'det'},
                    'data'
                ),
            }
        },
        inputs = {
            'results_download_button': {
                'n_clicks': Input({'type': 'results-download-btn', 'page': ALL, 'key': 'det'}, 'n_clicks'),
            },
            'modal_close_button': {
                'n_clicks': Input(
                    {'type': 'modal-close-btn', 'page': ALL, 'key': 'det-download-confirm'},
                    'n_clicks'
                )
                
            },
            'results_predownload_button': {
                'n_clicks': Input({'type': 'results-predownload-btn', 'page': 'model_configuration', 'key': ALL}, 'n_clicks'),
            },
        },
        state = {
            'modal': {
                'ids': State(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'det-download-confirm'},
                    'id'
                )
            },
            'options': {
                'values': State(
                    {'type': 'det-result-download-option', 'page': ALL, 'key': ALL},
                    'value'
                ),
                'ids': State(
                    {'type': 'det-result-download-option', 'page': ALL, 'key': ALL},
                    'id'
                )
            },
            'download': {
                'ids': State(
                    {'type': 'results-download-component', 'page': ALL, 'key': 'det'},
                    'id'
                )
            },
            'toast': {
                'ids':  State(
                    {'type': 'result-download-feedback-toast', 'page': ALL, 'key': 'det'},
                    'id'
                ),
            },
            'information': {
                'values': State(
                    {'type': 'result-download-information', 'page': ALL, 'key': 'det'},
                    'data'
                ),
                'ids': State(
                    {'type': 'result-download-information', 'page': ALL, 'key': 'det'},
                    'id'
                ),
            },
            'active_project_id': State('active-project-id', 'data'),
        },
        prevent_initial_call = True
    )
    def confirm_det_results_download(
        results_download_button,
        modal_close_button,
        results_predownload_button,
        modal,
        options,
        download,
        toast,
        information,
        active_project_id,
    ):
            
        n_modals = len(modal['ids'])
        n_downloads = len(download['ids'])
        n_toast = len(toast['ids'])
        n_information = len(information['ids'])
        rval: dict[str, Any] = dict(
            modal = dict(is_opens = [no_update] * n_modals),
            download = dict(datas = [no_update] * n_downloads),
            toast = dict(
                children = [no_update] * n_toast,
                is_opens = [no_update] * n_toast
            ),
            information = dict(
                values = [no_update] * n_information
            )
        )

        clicked = callback_utils.get_clicked_trigger()
        if clicked is None or not clicked.is_pattern():
            return rval
        trig_id = cast(dict, clicked.id)

        match trig_id.get('type'):
            case 'results-predownload-btn':
                config_index_str = trig_id.get('key')
                rval['modal']['is_opens'] = [True] * n_modals
                rval['information']['values'] = [config_index_str] * n_information
                return rval
            case 'results-download-btn':
                rval['modal']['is_opens'] = [False] * n_modals
                if n_information == 0:
                    rval['toast']['children'] = ['Unable to determine configuration'] * n_toast
                    rval['toast']['is_opens'] = [True] * n_toast
                    return rval
                config_index_str = information['values'][0]
                if config_index_str is None:
                    rval['toast']['children'] = ['Unable to determine configuration'] * n_toast
                    rval['toast']['is_opens'] = [True] * n_toast
                    return rval
                config_index = int(str(config_index_str).lstrip('config-'))-1

                proj = app.project_provider.get_project(active_project_id)
                configurations = proj.metamodels

                if config_index >= len(configurations):
                    rval['toast']['children'] = ['Configuration index out of range'] * n_toast
                    rval['toast']['is_opens'] = [True] * n_toast
                    return rval
                
                mm = configurations[config_index]

                if mm is None:
                    rval['toast']['children'] = ['Could not retrieve the configuration'] * n_toast
                    rval['toast']['is_opens'] = [True] * n_toast
                    return rval

                mm.model.reattach_results(app.results_provider)
                
                #if mm.model.dirty or mm.finance.dirty:
                #    rval['toast']['children'] = ['Deterministic results not run for current configuration'] * n_toast
                #    rval['toast']['is_opens'] = [True] * n_toast
                #    return rval
                
                page = trig_id.get('page')
                
                opts = callback_utils.get_options(
                    options['ids'],
                    options['values'],
                    page,
                    ['contents-option', 'format-option']
                )
                
                to_export = export.export_results(
                    'det',
                    app.project_provider,
                    app.results_provider,
                    active_project_id,
                    contents_option = opts.get('contents-option', 'result'),
                    format_option = opts.get('format-option', 'csv'),
                    result_level = 'metamodel'
                )

                if to_export is None:
                    rval['toast']['children'] = ['Deterministic results not available for current configuration'] * n_toast
                    rval['toast']['is_opens'] = [True] * n_toast
                    return rval
                
                for idx, id in enumerate(download['ids']):
                    if id['page'] == page:
                        rval['download']['datas'][idx] = to_export
            case _:
                rval['modal']['is_opens'] = [False] * n_modals
        return rval
