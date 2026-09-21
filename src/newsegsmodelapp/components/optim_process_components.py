
from dash import dcc, html
from dash_bootstrap_components._components.Modal import Modal as dbc_Modal
from dash_bootstrap_components._components.ModalHeader import ModalHeader as dbc_ModalHeader
from dash_bootstrap_components._components.ModalBody import ModalBody as dbc_ModalBody
from dash_bootstrap_components._components.ModalTitle import ModalTitle as dbc_ModalTitle
from dash_bootstrap_components._components.ModalFooter import ModalFooter as dbc_ModalFooter
from dash_bootstrap_components._components.Button import Button as dbc_Button
from dash_bootstrap_components._components.Toast import Toast as dbc_Toast

from newsegsmodelframework.newsegssensitivity import optim

def optim_process_components(**kwargs):
    return [
        dbc_Modal(
            [
            dbc_ModalHeader(dbc_ModalTitle('Start system optimisation')), # pyright: ignore[reportCallIssue]
            dbc_ModalBody([
                html.H3('Automatically optimise system size'),
                html.P((
                    'This automated process can take a substantial amount of time, ' \
                    'dependent on the complexity of the model, the number of ' \
                    'parameters to be optimised, and the optimisation method. '
                    'Before running, we advise taking the following steps:' \
                )),
                html.P((
                    '- Check the measure you want to optimise against - ' \
                    ' discounting can have a major impact on the location of the ' \
                    ' optimal point.'
                )),
                html.P((
                    '- Look at the marginal values of the measure against each of the ' \
                    'parameters. If the plot does not show a "peak" within the range then ' \
                    'it is likely to move to the bound of its range. Check if that ' \
                    'bound is plausible (e.g. can 4 MW of wind generation be exported ' \
                    'from the site, and is it physically big enough?). It is preferable ' \
                    'to set the value of these parameters and remove them from ' \
                    'optimisation, as gradient methods tend not to work well at the ' \
                    'boundary.'
                )),
                html.P((
                    '- All optimisation methods are sensitive to the starting parameter ' \
                    'values. Check that the current value is close to the "peak" in the ' \
                    'marginal plot to avoid getting trapped in a local maximum. However, ' \
                    'in complex cases where the interaction between parameters has a ' \
                    'strong and inconsistent impact on the measure, it is not guaranteed ' \
                    'that you will find the "global" maximum over the N-dimensional ' \
                    'parameter volume.'
                )),
                html.P((
                    '- The optimisation method can impact how long it takes to find ' \
                    'the optimal point, if it can be found at all. The default ' \
                    '(Nelder-Mead) is good at finding the optimum, but not as robust as ' \
                    'L-BFGS-B to a "rough" function. Powell optimisation is extremely '
                    'robust and simple, but requires a lot of function evaluations.'
                )),
                html.H3('Optimisation method:'),
                dcc.Dropdown(
                    options = optim.OPTIMISATION_METHODS,
                    value = optim.OPTIMISATION_METHODS[0],
                    searchable = False,
                    multi = False,
                    clearable = False,
                    id = {
                        'type': 'result-table-option', 'purpose': 'optim-method',
                        'supersection': 'optim', 'section': 'run',
                        'key': 'optim_run_metamodel', 'subindex': 0
                    },
                    persistence = True
                ),
            ]), # pyright: ignore[reportCallIssue]
            dbc_ModalFooter([
                dbc_Button(
                    'OK',
                    id = 'btn-action-optim-run-metamodel',
                    #  id = {
                    #     'type': 'action-button', 'purpose': 'request-process',
                    #     'supersection': 'optim', 'section': 'run',
                    #     'key': 'optim_run_metamodel', 'subindex': 0,
                    # },
                    n_clicks = 0
                ), # pyright: ignore[reportCallIssue]
                dbc_Button(
                    'Cancel',
                    id = 'btn-optim-confirm-abort',
                    className = 'ms-auto',
                    n_clicks = 0
                ) # pyright: ignore[reportCallIssue]
            ])
        ],
        id = 'modal-optim-confirm',
        is_open = False,
        size = 'xl',
    ),
    dbc_Toast(
        ['Optimisation unsuccessful'],
        id = {'type': 'feedback-toast', 'page': kwargs.get('page_type', 'None'), 'key': 'optim'},
        header = 'Optimisation exit',
        icon = 'warning',
        dismissable = True,
        is_open = False,
        duration = 5000,
        style = {'position': 'fixed', 'top': 66, 'right': 10, 'width': 350},
    ), # pyright: ignore[reportCallIssue]
    dcc.Store(id={'type': 'trigger', 'page': kwargs.get('page_type', 'None'), 'key': 'optim-run-postprocess'}, data = []),
]