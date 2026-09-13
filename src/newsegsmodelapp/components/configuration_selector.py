import base64
import json
from typing import Any, Sequence, cast

from dash import ALL, Input, Output, State, ctx, dcc, html, no_update
from dash_bootstrap_components._components.Button import Button as dbc_Button
from dash_bootstrap_components._components.Row import Row as dbc_Row
from dash_bootstrap_components._components.Col import Col as dbc_Col
from dash.exceptions import PreventUpdate
import pathvalidate

from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.components import export
from newsegsmodelapp.components.export import metamodel_to_config_file
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelapp.newsegsbrowser import icons
from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
from newsegsmodelframework.util import jsonfuncs

# -----------------------------------------------
# Layout
# -----------------------------------------------

def create_config_selector_headerbutton(
    config_index: int = 0,
    metamodel: NewsegsMetaModel | None = None,
    is_focussed: bool | None = None,
):
    if is_focussed:
        do_outline = False
    else:
        do_outline = True
    
    contents = dbc_Button(
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

_PLACEHOLDER_NAMES = set('Configuration Name')

def create_single_configuration_selector_row(
    config_index: int = 0,
    metamodel: NewsegsMetaModel | None = None,
    is_focussed: bool | None = None,
    reference_size: int = 20,
):
    
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
    
    if metamodel is None:
        config_name = 'Configuration Name'
    else:
        config_name = metamodel.name

    is_focussed = True if is_focussed is None else is_focussed
    
    if config_name in _PLACEHOLDER_NAMES:
        # Assume this is a placeholder and do not populated the Input Value
        contents.append(
            dcc.Input(
                placeholder = config_name,
                debounce = True,
                type = 'text',
                id = {'type': 'config-name-input', 'index': config_index},
                size = str(reference_size),
                className = ' configuration-selector-row-name-input'
            )
        )
    else:
        contents.append(
            dcc.Input(
                value = config_name,
                debounce = True,
                type = 'text',
                id = {'type': 'config-name-input', 'index': config_index},
                size = str(reference_size * 1.3),
                className = 'configuration-selector-row-name-input'
            )
        )

    button_container_children = []
    
    button_container_children += [
        dbc_Button(
            html.I(
                className = icons.get_icon('config-focus', style_name = 'raw'),
                style={'display': 'inline'}
            ),
            color = 'primary',
            id = {'type': 'config-focus-btn', 'index': config_index},
            outline = not(is_focussed),
            title = 'Focus configuration',
        ),

        dbc_Button(
            html.I(
                className = icons.get_icon('config-duplicate', style_name = 'raw'),
                style={'display': 'inline'}
            ),
            color="primary",
            id = {'type': 'config-dup-btn', 'index': config_index},
            outline = True,
            title = 'Duplicate configuration'
        ),

        dbc_Button(
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
            dbc_Button(
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
            
        dbc_Button(
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
            dbc_Button(
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
        dbc_Row([
            dbc_Col([
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
    return html.Div([
        
        html.Div(
            [],
            id = {'type': 'metamodel-input-container', 'supersection': 'configurations', 'section': 'configuration-selector'}
        ),
        dcc.Download(id='download-config-json'),
        dcc.Store(id='n_active_conf', data = '{"n": 1}')
    ])

# -----------------------------------------------
# Callbacks
# -----------------------------------------------

def _create_configuration_rows_for_metamodels(
    metamodels: Sequence[NewsegsMetaModel],
    focussed_index: int = 0,
):
    contents = [
        create_single_configuration_selector_row(
            i, mm, i == focussed_index
        ) for i, mm in enumerate(metamodels)
    ]
    return contents

def _create_configuration_header_elements_for_metamodels(
    metamodels: Sequence[NewsegsMetaModel],
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
    @app.callback(
        Output({'type': 'metamodel-input-container', 'supersection': ALL, 'section': 'configuration-selector'}, 'children'),
        Output({'type': 'metamodel-input-container', 'supersection': ALL, 'section': 'configuration-header-selector'}, 'children'),

        Input('active-project-id', 'data'),
        State({'type': 'metamodel-input-container', 'supersection': ALL, 'section': 'configuration-selector'}, 'id'),
        State({'type': 'metamodel-input-container', 'supersection': ALL, 'section': 'configuration-header-selector'}, 'id'),

    )
    def population_configuration_selector(
        active_project_id,
        configuration_container_ids,
        configuration_header_ids,
    ):
        if active_project_id is None or len(configuration_container_ids) == 0:
            raise PreventUpdate

        proj = cast(NewsegsProject, app.project_provider.get_component(active_project_id))
        config_rows = _create_configuration_rows_for_metamodels(proj.metamodels, proj.get_focussed_metamodel_index())
        header_elements = _create_configuration_header_elements_for_metamodels(proj.metamodels, proj.get_focussed_metamodel_index())

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

        proj = app.project_provider.get_project(active_project_id)

        mm_index = trig['index']
        new_name = callback_utils.get_triggered_value()

        mm = proj.metamodels[mm_index]
        if not mm:
            raise PreventUpdate
        mm.name = new_name
        mm.revision += 1
        app.project_provider.upsert_component(proj)

        # Trigger a rebuild of the page in case the name is baked into e.g. button titles.
        return active_project_id

    # Duplicate
    @app.callback(
        Output('active-project-id', 'data', allow_duplicate = True),

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
        new_mm = app.project_provider.metamodel_provider.duplicate_component(ref_mm.id) # pyright: ignore[reportAttributeAccessIssue]
        new_mm.name = new_mm.name + ' - Copy'
        new_mm.revision += 1
        proj.metamodels.append(new_mm) # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]
        proj.set_focussed_metamodel(new_mm.id)
        
        app.project_provider.upsert_component(proj)

        # Trigger interface update
        return active_project_id

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

        proj.revision += 1
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
        trig = ctx.triggered_id
        if trig is None or len(ctx.triggered) > 1 or not callback_utils.get_triggered_value() or not active_project_id:
            raise PreventUpdate

        mm_index = trig['index']
        proj = app.project_provider.get_project(active_project_id)
        if proj.get_focussed_metamodel_index() == mm_index:
            raise PreventUpdate

        proj.set_focussed_metamodel_index(mm_index)
        proj.revision += 1
        app.project_provider.upsert_component(proj)

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

        fn = odict.get('config_name','metamodel_configuration') + ".json"
        fn = pathvalidate.sanitize_filename(fn)
        
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

        try:
            working_conf = trig_val
            ctype, cstr = working_conf.split(',')
            cfg = json.loads(base64.b64decode(cstr))
        except json.JSONDecodeError as e:
            print(e)
            raise PreventUpdate

        mm_config = cfg.get('metamodel')
        constr = find_constructor(mm_config['constructor_class'], mm_config['class'])
        print(constr)
        if not constr:
            raise PreventUpdate

        mm_new = cast(NewsegsMetaModel, constr(mm_config))
        # Caution: We cannot safely add this new metamodel to the project until we have generated new ids
        # for each component.
        mm_new.anonymise_ids()
        print(mm_new)

        proj = app.project_provider.get_project(active_project_id)
        proj.metamodels.append(mm_new) # pyright: ignore[reportAttributeAccessIssue]
        proj.set_focussed_metamodel(mm_new.id)
        proj.revision += 1
        app.project_provider.upsert_component(proj)

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

        trig_id = ctx.triggered_id
        
        if trig_id is None:
            return rval
        trig_val = ctx.triggered
        if len(trig_val) > 1 or trig_val[0].get('value') is None:
            return rval
        
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
                    rval['toast']['children'] = ['Could not retrieve metamodel'] * n_toast
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
                    config_index,
                    opts.get('contents-option', 'result'),
                    opts.get('format-option', 'csv')
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
