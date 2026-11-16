"""The download of results: the buttons which open the download dialog, the dialog, and its callbacks.

There is a dialog for each type of result (`det`, `dsa` or `psa`), on the page which shows those results. It is opened
by a button of the same type, which targets the focussed configuration (`target='focussed'`) or a configuration by its
id. The dialog chooses whether to download the results of that configuration or of every configuration in the project,
as csv or xlsx, and whether to include the configurations; see `export` for the files.

Ids, all with `'result': <type>`:

- `{'type': 'results-download-open', 'result', 'target'}`: the buttons which open the dialog.
- `{'type': 'results-download-modal', 'result'}`: the dialog.
- `{'type': 'results-download-scope' | 'results-download-format' | 'results-download-include', 'result'}`: its options.
- `{'type': 'results-download-ok' | 'results-download-cancel', 'result'}`: its buttons.
- `{'type': 'results-download-target', 'result'}`: store of the target of the button which opened the dialog.
- `{'type': 'results-download', 'result'}`: the `dcc.Download`.
- `{'type': 'results-download-feedback', 'result'}`: toast reporting configurations without results, or failure.
"""
import logging
from typing import Any, cast

from dash import ALL, Input, Output, State, dcc, html, no_update
from dash.exceptions import PreventUpdate

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.components import callback_utils, export, icons
from newsegsmodelapp.dash_extension import NewsegsDash
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

logger = logging.getLogger(__name__)

RESULT_TYPES = ('det', 'dsa', 'psa')

FOCUSSED = 'focussed'
"""Target of a button which downloads the results of the focussed configuration."""

SCOPE_ONE = 'one'
SCOPE_ALL = 'all'
INCLUDE_CONFIGURATION = 'configuration'

def component_id(type_: str, result_type: str) -> dict[str, str]:
    """The id of a component of the download dialog of a type of result.

    Args:
        type_: The type of the component, e.g. `results-download-modal`.
        result_type: `det`, `dsa` or `psa`.

    Returns:
        The id.
    """
    return {'type': type_, 'result': result_type}

def open_button_id(result_type: str, target: str = FOCUSSED) -> dict[str, str]:
    """The id of a button which opens the download dialog.

    Args:
        result_type: `det`, `dsa` or `psa`.
        target: `focussed`, or the id of a configuration (metamodel).

    Returns:
        The id.
    """
    return {'type': 'results-download-open', 'result': result_type, 'target': target}

def create_results_download_button(
    result_type: str,
    target: str = FOCUSSED,
    title: str | None = None,
    **kwargs,
):
    """Create a button which opens the download dialog of a type of result.

    Args:
        result_type: `det`, `dsa` or `psa`.
        target: `focussed`, or the id of a configuration (metamodel) whose results the dialog downloads.
        title: Tooltip of the button; by default `Download <type> results`.
        **kwargs: Further arguments of the button, e.g. `style`.

    Returns:
        The button.
    """
    kwargs.setdefault('color', 'secondary')
    kwargs.setdefault('outline', True)
    return dbc.Button(
        html.I(
            className = icons.get_icon('results-download', style_name = 'raw'),
            style = {'display': 'inline'}
        ),
        id = open_button_id(result_type, target),
        title = title or f'Download {export.RESULT_TYPE_LABELS[result_type]} results',
        **kwargs,
    )

def _scope_options(configuration_name: str | None = None) -> list[dict[str, str]]:
    one = 'This configuration' if configuration_name is None else f'This configuration ({configuration_name})'
    return [
        {'label': one, 'value': SCOPE_ONE},
        {'label': 'All configurations', 'value': SCOPE_ALL},
    ]

def create_results_download_components(result_type: str) -> list:
    """Create the download dialog of a type of result, with its store, `dcc.Download` and feedback toast.

    Put once on the page which shows the results, with the buttons from `create_results_download_button`.

    Args:
        result_type: `det`, `dsa` or `psa`.

    Returns:
        List of components.
    """
    label = export.RESULT_TYPE_LABELS[result_type]
    return [
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle(f'Download {label} results')),
                dbc.ModalBody([
                    html.H3('Configurations:'),
                    dcc.RadioItems(
                        _scope_options(),
                        SCOPE_ONE,
                        id = component_id('results-download-scope', result_type),
                    ),
                    html.H3('Format:'),
                    dcc.RadioItems(
                        [
                            {'label': 'Comma separated values (.csv): a file per configuration', 'value': 'csv'},
                            {'label': 'Microsoft® Excel® Spreadsheet (.xlsx): a sheet per configuration', 'value': 'xlsx'},
                        ],
                        'csv',
                        id = component_id('results-download-format', result_type),
                    ),
                    html.H3('Contents:'),
                    dcc.Checklist(
                        [{'label': 'Include the configurations (.json), to upload them again', 'value': INCLUDE_CONFIGURATION}],
                        [],
                        id = component_id('results-download-include', result_type),
                    ),
                ]),
                dbc.ModalFooter([
                    dbc.Button(
                        'Download',
                        id = component_id('results-download-ok', result_type),
                        n_clicks = 0,
                    ),
                    dbc.Button(
                        'Cancel',
                        id = component_id('results-download-cancel', result_type),
                        className = 'ms-auto',
                        n_clicks = 0,
                    ),
                ]),
            ],
            id = component_id('results-download-modal', result_type),
            is_open = False,
        ),
        dcc.Store(id = component_id('results-download-target', result_type), data = FOCUSSED),
        dcc.Download(id = component_id('results-download', result_type)),
        dbc.Toast(
            [],
            id = component_id('results-download-feedback', result_type),
            header = f'Download {label} results',
            icon = 'warning',
            dismissable = True,
            is_open = False,
            duration = 8000,
            style = {'position': 'fixed', 'top': 66, 'right': 10, 'width': 350, 'zIndex': 2000},
        ),
    ]

def _names(names: list[str]) -> str:
    return ', '.join(names)

def add_results_download_callbacks(app: NewsegsDash):
    """Bind the callbacks of the download dialogs: opening and closing them, and downloading.

    Args:
        app: The Dash app.
    """
    for result_type in RESULT_TYPES:
        _add_results_download_callback(app, result_type)

def _add_results_download_callback(app: NewsegsDash, result_type: str):
    label = export.RESULT_TYPE_LABELS[result_type]

    @app.callback(
        output = dict(
            modal_is_open = Output(component_id('results-download-modal', result_type), 'is_open'),
            scope_options = Output(component_id('results-download-scope', result_type), 'options'),
            scope_value = Output(component_id('results-download-scope', result_type), 'value'),
            target = Output(component_id('results-download-target', result_type), 'data'),
            download = Output(component_id('results-download', result_type), 'data'),
            feedback = dict(
                children = Output(component_id('results-download-feedback', result_type), 'children'),
                icon = Output(component_id('results-download-feedback', result_type), 'icon'),
                is_open = Output(component_id('results-download-feedback', result_type), 'is_open'),
            ),
        ),
        inputs = dict(
            open_clicks = Input(open_button_id(result_type, ALL), 'n_clicks'), # pyright: ignore[reportArgumentType]
            ok_clicks = Input(component_id('results-download-ok', result_type), 'n_clicks'),
            cancel_clicks = Input(component_id('results-download-cancel', result_type), 'n_clicks'),
        ),
        state = dict(
            scope = State(component_id('results-download-scope', result_type), 'value'),
            format_option = State(component_id('results-download-format', result_type), 'value'),
            include = State(component_id('results-download-include', result_type), 'value'),
            target = State(component_id('results-download-target', result_type), 'data'),
            active_project_id = State('active-project-id', 'data'),
        ),
        prevent_initial_call = True,
    )
    def download_results(
        open_clicks,
        ok_clicks,
        cancel_clicks,
        scope,
        format_option,
        include,
        target,
        active_project_id,
    ):
        # The open buttons fire, without clicks, when the configuration selector redraws them
        clicked = callback_utils.get_clicked_trigger()
        if clicked is None or not active_project_id:
            raise PreventUpdate

        rval: dict[str, Any] = dict(
            modal_is_open = no_update,
            scope_options = no_update,
            scope_value = no_update,
            target = no_update,
            download = no_update,
            feedback = dict(children = no_update, icon = no_update, is_open = no_update),
        )

        def feedback(message: str, icon: str = 'warning'):
            rval['feedback'] = dict(children = message, icon = icon, is_open = True)
            return rval

        provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)
        lproj = provider.get_lightweight_project(active_project_id)
        metamodel_ids = [lmm.id for lmm in lproj.metamodels]

        def resolve(target_: str | None) -> str | None:
            """The id of the target's metamodel, if it is in the project."""
            if target_ in (None, FOCUSSED):
                return lproj.metamodels[lproj.focussed_metamodel_index].id
            return target_ if target_ in metamodel_ids else None

        trig_type = clicked.type
        if trig_type == 'results-download-open':
            new_target = cast(dict, clicked.id)['target']
            mm_id = resolve(new_target)
            name = next((lmm.name for lmm in lproj.metamodels if lmm.id == mm_id), None)
            rval.update(
                modal_is_open = True,
                scope_options = _scope_options(name),
                target = new_target,
            )
            if new_target != FOCUSSED:
                # The button of a configuration's row is for that configuration
                rval['scope_value'] = SCOPE_ONE
            return rval

        rval['modal_is_open'] = False
        if trig_type != 'results-download-ok':
            return rval

        if scope == SCOPE_ALL:
            selected = metamodel_ids
        else:
            mm_id = resolve(target)
            if mm_id is None:
                return feedback('The configuration has been removed from the project.')
            selected = [mm_id]

        try:
            result = export.export_results(
                cast(export.ResultType, result_type),
                app.project_provider,
                app.results_provider,
                active_project_id,
                metamodel_ids = selected,
                format_option = format_option or 'csv',
                include_configuration = INCLUDE_CONFIGURATION in (include or []),
            )
        except Exception:
            logger.exception(
                'Could not export %s results of project %s; Metamodels: %s',
                result_type, active_project_id, selected,
            )
            return feedback(f'The {label} results could not be downloaded.', icon = 'danger')

        if result.download is None:
            if len(selected) == 1:
                return feedback(f'{result.missing[0]} has no {label} results to download.')
            return feedback(f'No configuration has {label} results to download.')

        rval['download'] = result.download
        if result.missing:
            return feedback(f'Configurations without {label} results were left out: {_names(result.missing)}.', icon = 'info')
        return rval
