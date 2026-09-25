"""
Layout and callbacks for interfacing with Variables
"""
from typing import Any, Sequence
from collections import OrderedDict

from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_daq as daq

from newsegsmodelapp.components.input_components import create_numeric_variable_parameter_input
from newsegsmodelapp.components.variable_identification import VariableInstanceParameterComponentID
from newsegsmodelframework.newsegsvariable import variable

def _autoformat(val) -> str:
    if isinstance(val, float):
        return f'{val:,.1f}' # If you want other precision, deal with that before passing it in
    elif isinstance(val, int):
        return f'{val:d}'
    elif isinstance(val, str):
        return val
    else:
        return str(val)

def create_dsa_input_scalar_numeric_header(
    label: str,
    value,
    lower,
    upper,
):
    value = _autoformat(value)
    lower = _autoformat(lower)
    upper = _autoformat(upper)
    return [
        html.H4(
            label,
        ),
        html.Div([
            html.Span(
                value
            ),
            html.Div([
                '[',
                html.Span(
                    lower
                ),
                ', ',
                html.Span(
                    upper
                ),
                ']'

            ],
            className = 'dsa-configuration-summaryinfo-dsa-live-values'
            )
            
        ],
        className='dsa-configuration-summaryinfo'
        )
    ]

def create_dsa_input_vector_numeric_header(
        label: str,
        type_id: str,
        key: str,
        section: str | None = None,
): 
    return [
        html.H4(
            label,
        ),
        html.Div([
            html.Span(
                '('
                + ', '.join([f'{x:,.2f}' for x in [1.,2.]])
                + ")"
            ),
            html.Div([
                '[',
                html.Span(
                    '('
                    + ', '.join([f'{x:,.2f}' for x in [.9,1.8]])
                    + ")"
                ),
                ', ',
                html.Span(
                    '('
                    + ', '.join([f'{x:,.2f}' for x in [1.1,2.2]])
                    + ")"
                ),
                ']'

            ],
            className = 'dsa-configuration-summaryinfo-dsa-live-values'
            )
            
        ],
        className='dsa-configuration-summaryinfo'
        )
    ]

def create_dsa_input_vector_parameter_input(
    parameter_names: str | Sequence[str] | OrderedDict[str, Sequence[str]],
    parameter_types: Sequence[variable.PARAMETER_TYPE],
    type_id: str,
    key: str,
    section: str | None = None,
):
    are_scalars = [i for i, x in enumerate(parameter_types) if x == 'scalar']
    are_vectors = [i for i, x in enumerate(parameter_types) if x == 'vector']
    are_matrices = [i for i, x in enumerate(parameter_types) if x == 'matrix']

    if isinstance(parameter_names, OrderedDict):
        param_class = list(parameter_names.keys())
    elif isinstance(parameter_names, str):
        param_class = [parameter_names]
    else:
        param_class = parameter_names

    def make_input(placeholder: Any):
        return dbc.Input(type = 'number', debounce = True, placeholder = placeholder, class_name = 'numeric-input') # pyright: ignore[reportCallIssue]

    def make_inputgroup(label: str, placeholder: Any):
        return dbc.InputGroup([
            dbc.InputGroupText(label+':'), # pyright: ignore[reportCallIssue]
            make_input(placeholder)
        ]) # pyright: ignore[reportCallIssue]
    
    rval = []
    for idx in are_scalars:
        rval += [make_inputgroup(str(param_class[idx]), param_class[idx])]
    
    if not isinstance(parameter_names, OrderedDict):
        for idx in are_vectors:
            rval += [html.Div([
                html.P(param_class[idx]),
                make_inputgroup('Value[0]', '[0]')
            ])]
    else:
        for idx in are_vectors:
            rval += [html.Div([
                html.Table([
                    html.Thead([
                        html.Th(
                            param_class[idx]     
                        )
                    ]),
                    html.Tbody([
                        html.Tr(html.Td(make_inputgroup(x, x))) for x in parameter_names[param_class[idx]]
                    ])
                ])
            ])]
    
    for idx in are_matrices:
        # TODO: Make this responsive to a variable's dimensions
        NVAL = 2
        rval += [html.Div([
                html.Table([
                    html.Thead([
                        html.Th(
                            param_class[idx],
                            colSpan = NVAL
                        )
                    ]),
                    html.Tbody([
                        html.Tr([
                            html.Td(make_input(f'[{x},{y}]'))
                            for y in range(NVAL)
                        ])
                        for x in range(NVAL)
                    ]),
                ])
            ])]
        
    return rval
    
def _create_numeric_inputgroup_from_var(
    var: variable.NumericScalarVariable,
    parameter_name: str,
    parameter_index: int = 0,
    min: int | float | None = 0,
    max: int | float | None = None,
    stepscale: float = 1.,
    type_id: str | None = None,
    supersection: str = 'deterministic',
    purpose: str = 'parameter',
):
    if type_id is None:
        type_id = f'single-input-config'
    
    variable_id = VariableInstanceParameterComponentID.from_variable(
        var,
        type = type_id,
        supersection = supersection,
        purpose = purpose,
        parameter_index = parameter_index
    )
    
    return dbc.InputGroup(
        [
            dbc.InputGroupText(parameter_name + ":"), # pyright: ignore[reportCallIssue]
            
            create_numeric_variable_parameter_input(
                variable_id,
                value = var.raw_parameters[parameter_index], # pyright: ignore[reportArgumentType]
                placeholder = parameter_name,
                min = min,
                max = max,
                step = var.interface_step * stepscale if var.interface_step else 1
            ),
        ]
    ) # pyright: ignore[reportCallIssue]

def create_dsa_bounds_inputs_scalar(
    bounds_type: variable.DSA_BOUNDS_TYPE,
    var: variable.NumericScalarVariable,
):
    type_id_lower = f'input-dsabound-lower'
    type_id_upper = f'input-dsabound-upper'

    variable_id_lower = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'single-input-config',
        supersection = 'dsa',
        purpose = 'bound-lower',
    )

    variable_id_upper = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'single-input-config',
        supersection = 'dsa',
        purpose = 'bound-upper',
    )

    match bounds_type:
        case 'absolute' | 'relative' | 'offset':
            if bounds_type == 'relative':
                step_size = 0.05
            else:
                step_size = float(f'{var.deterministic_value / 10:2g}')
                if step_size == 0:
                    step_size = 0.05

            return [
                dbc.InputGroup([
                    dbc.InputGroupText('Lower:'), # pyright: ignore[reportCallIssue]
                    
                    create_numeric_variable_parameter_input(
                        variable_id_lower,
                        value = var.dsa_lower, # pyright: ignore[reportArgumentType]
                        step = step_size
                    ),
                ]
                ), # type: ignore
                dbc.InputGroup([
                    dbc.InputGroupText('Upper:'), # pyright: ignore[reportCallIssue]
                    create_numeric_variable_parameter_input(
                        variable_id_upper,
                        value = var.dsa_upper, # pyright: ignore[reportArgumentType]
                        step = step_size
                    ),
                ]
                ),
            ]
        case 'interval':
            return [
                dbc.InputGroup([
                    dbc.InputGroupText('Confidence:'), # pyright: ignore[reportCallIssue]
                    create_numeric_variable_parameter_input(
                        variable_id_lower,
                        value = var.dsa_lower, # pyright: ignore[reportArgumentType]
                    )
                ])
            ] 
        
def create_dsa_bounds_input_vector(
    bounds_type: variable.DSA_BOUNDS_TYPE,
    type_id: str,
    key: str,
    section: str | None = None,
    #var: variable.Variable
):
    
    def make_input(placeholder: Any):
        return dbc.Input(type = 'number', debounce = True, placeholder = placeholder) # pyright: ignore[reportCallIssue]
    
    # TODO: Make this responsive to the variable
    n_values = 2
    match bounds_type:
        case 'absolute' | 'relative' | 'offset':
            return [
                html.Div([
                    html.Table([
                        html.Thead([
                            html.Th('Lower'),
                        ]),
                        html.Tbody([
                            html.Tr(html.Td(make_input(x))) for x in range(n_values)
                        ])
                    ])
                ]),
                html.Div([
                    html.Table([
                        html.Thead([
                            html.Th('Upper'),
                        ]),
                        html.Tbody([
                            html.Tr(html.Td(make_input(x))) for x in range(n_values)
                        ])
                    ])
                ]),
            ]
        case 'interval':
            return [
                html.Div([
                    html.Table([
                        html.Thead([
                            html.Th('Confidence'),
                        ]),
                        html.Tbody([
                            html.Tr(html.Td(make_input(x))) for x in range(n_values)
                        ])
                    ])
                ])
            ] 

def create_dsa_bound_type_selector(
    permitted_dsa_bounds,
    selected_bound,
    var: variable.Variable,
):
    id_ = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'input-dropdown',
        supersection = 'dsa',
        purpose = 'dsaboundtype'
    )
    return [
        dcc.Dropdown(
            permitted_dsa_bounds,
            selected_bound,
            id = id_.as_dict(),
            searchable = False,
            clearable = False
        )
    ]

def compose_dsa_input(
    header_component,
    parameter_component,
    dsa_bound_type_selector,
    dsa_bound_component,
    var: variable.Variable,
):
    overall_input_id = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'input-component',
        supersection = 'dsa',
        purpose = 'input-group-container',
    )

    toggle_id = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'input-toggle',
        supersection = 'dsa',
        purpose = 'dsa-active'
    )

    header_id = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'single-input-header',
        supersection = 'dsa',
        purpose = 'header',
    )

    bounds_container_id = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'input-component',
        supersection = 'dsa',
        purpose = 'bounds-container'
    )

    trigger_id = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'input-group-config-update-trigger',
        supersection = 'dsa',
        purpose = 'trigger',
    )

    if var.dsa_selected:
        cn = 'dsa-input-single-value-block'
    else:
        cn = 'dsa-input-single-value-block deselected'

    return html.Div([
        daq.ToggleSwitch(
            #vertical = True,
            className = 'dsa-toggle',
            size = 30,
            value = var.dsa_selected,
            id = toggle_id.as_dict(),
        ),
        html.Details([
            html.Summary(
                header_component,
                className='dsa-configuration-summary',
                id = header_id.as_dict()
            ),
            html.Div((
                parameter_component
                + dsa_bound_type_selector
                + [
                    html.Span(
                        dsa_bound_component,
                        id = bounds_container_id.as_dict()
                    )
                ]
            ))
        ],
        ),
        dcc.Store(id = trigger_id.as_dict())
    ],
    className=cn,
    id = overall_input_id.as_dict(),
    )

def create_dsa_header(
    var: variable.ScalarVariable,
):
    if var.distribution.distribution == 'constant':
        fmt = _autoformat
    else:
        fmt = var.value_formatter
    label = f'{var.label} ({var.unit})'

    hdr = create_dsa_input_scalar_numeric_header(
        label, 
        fmt(var.deterministic_value),
        fmt(var.get_dsa_value('lower', True)),
        fmt(var.get_dsa_value('upper', True)),
    )
    
    return hdr


def create_dsa_input_scalar_constant(
    var: variable.ScalarVariable,
):
    return compose_dsa_input(
        create_dsa_header(var),
        [
             _create_numeric_inputgroup_from_var(
                var, 'Value', 0,  # pyright: ignore[reportArgumentType]
                min = var.interface_min, max = var.interface_max, 
                supersection = 'dsa' # pyright: ignore[reportArgumentType]
            ),
        ],
        create_dsa_bound_type_selector(
            ['absolute', 'relative', 'offset'],
            var.dsa_bounds_type,
            var,
        ),
        create_dsa_bounds_inputs_scalar(
            var.dsa_bounds_type,
            var, # pyright: ignore[reportArgumentType]
        ),
        var
    )


# A form element for a normally distributed variable
# e.g. a scaling factor for expected annual insolation
def create_dsa_input_scalar_normal(
    var: variable.NumericScalarVariable,
):
    return compose_dsa_input(
        create_dsa_header(var),
        [
            _create_numeric_inputgroup_from_var(
                var, 'Mean', 0, 
                min = var.interface_min, max = var.interface_max,
                supersection = 'dsa'
            ),
            _create_numeric_inputgroup_from_var(
                var, 'SD', 1, stepscale = 0.1,
                supersection = 'dsa'
            ),
        ],
        create_dsa_bound_type_selector(
            ['absolute', 'relative', 'offset', 'interval'],
            var.dsa_bounds_type,
            var,
        ),
        create_dsa_bounds_inputs_scalar(
            var.dsa_bounds_type,
            var,
        ),
        var
    )

def create_dsa_input_scalar_beta(
    var: variable.NumericScalarVariable,
):
    return compose_dsa_input(
        create_dsa_header(var),
        [
            _create_numeric_inputgroup_from_var(
                var, 'Mean', 0, min = var.interface_min, max = var.interface_max,
                supersection = 'dsa'
            ),
            _create_numeric_inputgroup_from_var(
                var, 'SD', 1, stepscale = 0.1,
                supersection = 'dsa'
            ),
        ],
        create_dsa_bound_type_selector(
            ['absolute', 'relative', 'offset', 'interval'],
            var.dsa_bounds_type,
            var,
        ),
        create_dsa_bounds_inputs_scalar(
            var.dsa_bounds_type,
            var,
        ),
        var
    )

def create_dsa_input_scalar_gamma(
    var: variable.NumericScalarVariable,
):
    type_id = f'input-{var.configuration_type}-config'
    return compose_dsa_input(
        create_dsa_header(var),
        [
            _create_numeric_inputgroup_from_var(
                var, 'Mean', 0, min = var.interface_min, max = var.interface_max,
                supersection = 'dsa'
            ),
            _create_numeric_inputgroup_from_var(
                var, 'SD', 1, stepscale = 0.1,
                supersection = 'dsa'
            ),
        ],
        create_dsa_bound_type_selector(
            ['absolute', 'relative', 'offset', 'interval'],
            var.dsa_bounds_type,
            var,
        ),
        create_dsa_bounds_inputs_scalar(
            var.dsa_bounds_type,
            var,
        ),
        var
    )

def create_psa_input_scalar_numeric_header(
    label: str,
    mean_value,
    std_value,
    ci95_lower,
    ci95_upper,
):
    mean_value = _autoformat(mean_value)
    std_value = _autoformat(std_value)
    ci95_lower = _autoformat(ci95_lower)
    ci95_upper = _autoformat(ci95_upper)
    return [
        html.H4(
            label,
        ),
        html.Div([
            html.Span(
                mean_value + ' ± ' + std_value
            ),
            html.Div([
                '(95% CI: ',
                html.Span(
                    ci95_lower
                ),
                ', ',
                html.Span(
                    ci95_upper
                ),
                ')'

            ],
            className = 'psa-configuration-summaryinfo-psa-live-values'
            )
            
        ],
        className='psa-configuration-summaryinfo'
        )
    ]

def create_psa_header(
    var: variable.ScalarVariable,
):
    if var.distribution.distribution == 'constant':
        fmt = _autoformat
    else:
        fmt = var.value_formatter
    if var.unit == '':
        label = var.label
    else:
        label = f'{var.label} ({var.unit})'

    ci = var.get_confidence_interval(0.95)
    hdr = create_psa_input_scalar_numeric_header(
        label,
        fmt(var.get_deterministic_value()),
        fmt(var.get_std()),
        fmt(ci[0]),
        fmt(ci[1])
    )

    return hdr

def create_psa_distribution_component(
    var: variable.Variable
):
    distname = var.distribution.distribution.title()
    return [
        html.P(
            'Distribution:',
            className = 'distribution-label-title'
        ),
        #html.Br(),
        html.P(
            distname,
            className = 'distribution-label-name'
        ),
    ]


def compose_psa_input(
    header_component,
    distribution_component,
    parameter_component,
    var: variable.Variable,
):
    overall_input_id = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'input-component',
        supersection = 'psa',
        purpose = 'input-group-container',
    )

    toggle_id = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'input-toggle',
        supersection = 'psa',
        purpose = 'psa-active',
    )

    header_id = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'single-input-header',
        supersection = 'psa',
        purpose = 'header'
    )

    trigger_id = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'input-group-config-update-trigger',
        supersection = 'psa',
        purpose = 'trigger',
    )

    if var.psa_selected:
        cn = 'psa-input-single-value-block'
    else:
        cn = 'psa-input-single-value-block deselected'

    return html.Div([
        daq.ToggleSwitch(
            className = 'psa-toggle',
            size = 30,
            value = var.psa_selected,
            id = toggle_id.as_dict(),
        ),
        html.Details([
            html.Summary(
                header_component,
                className = 'psa-configuration-summary',
                id = header_id.as_dict()
            ),
            html.Div((
                [html.Div(
                    distribution_component,
                    className = 'distribution-label',
                )]
                +parameter_component
            ))
        ]),
        dcc.Store(id = trigger_id.as_dict())
    ],
    className = cn,
    id = overall_input_id.as_dict(),
    )

def create_psa_input_scalar_constant(
    var: variable.ScalarVariable,
):
    return compose_psa_input(
        create_psa_header(var),
        create_psa_distribution_component(var),
        [
            _create_numeric_inputgroup_from_var(
                var, 'Value', 0, # pyright: ignore[reportArgumentType]
                min = var.interface_min, max = var.interface_max,
                supersection = 'psa'
            ),
        ],
        var
    )

def create_psa_input_twoparam(
    var: variable.NumericScalarVariable,    
):
    return compose_psa_input(
        create_psa_header(var),
        create_psa_distribution_component(var),
        [
            _create_numeric_inputgroup_from_var(
                var, 'Mean', 0, min = var.interface_min, max = var.interface_max,
                supersection = 'psa'
            ),
            _create_numeric_inputgroup_from_var(
                var, 'SD', 1, stepscale = 0.1,
                supersection = 'psa'
            ),
        ],
        var
    )

def create_psa_input_scalar_normal(
    var: variable.NumericScalarVariable,
):
    return create_psa_input_twoparam(var)

def create_psa_input_scalar_beta(
    var: variable.NumericScalarVariable,
):
    return create_psa_input_twoparam(var)

def create_psa_input_scalar_gamma(
    var: variable.NumericScalarVariable,
):
    return create_psa_input_twoparam(var)

def compose_optim_input(
    header,
    #positive_toggle,
    #bounded_toggle,
    bound_inputs,
    var
):
    toggle_id = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'input-toggle',
        supersection = 'optim',
        purpose = 'toggle-optim-active',
    )

    header_id = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'single-input-header',
        supersection = 'optim',
        purpose = 'header',
    )

    bounds_container_id = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'optim-bounds-inputcontainer',
        supersection = 'optim',
        purpose = 'container',
    )

    trigger_id = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'input-group-config-update-trigger',
        supersection = 'optim',
        purpose = 'trigger',
    )

    if var.optim_selected:
        cn = 'optim-input-single-value-block'
    else:
        cn = 'optim-input-single-value-block deselected'

    overall_input_id = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'input-component',
        supersection = 'optim',
        purpose = 'container'
    )

    return html.Div([
        daq.ToggleSwitch(
            className = 'optim-toggle',
            size = 30,
            value = var.optim_selected,
            id = toggle_id.as_dict(),
        ),
        html.Details([
            html.Summary(
                header,
                className = 'optim-configuration-summary',
                id = header_id.as_dict()
            ),
            html.Div((
                #[positive_toggle]
                #+[bounded_toggle]
                [html.Span(bound_inputs, id = bounds_container_id.as_dict())]
            ))
        ]),
        dcc.Store(id = trigger_id.as_dict())
    ],
    className= cn,
    id = overall_input_id.as_dict()
    )

def create_optim_header(var: variable.NumericScalarVariable, refvar: variable.NumericScalarVariable | None = None):
    if var.distribution.distribution == 'constant':
        fmt = _autoformat
    else:
        fmt = var.value_formatter

    if var.unit == '':
        label = var.label
    else:
        label = f'{var.label} ({var.unit})'

    section = var.interface_section
    if section is None:
        section = 'None'

    input_id = VariableInstanceParameterComponentID.from_variable(
        var,
        type = f'single-input-config',
        supersection = 'optim',
        purpose = 'parameter',
    )
    
    if refvar is not None:
        content = [
            html.Span([
                fmt(refvar.get_deterministic_value()), # pyright: ignore[reportArgumentType]
                ' -> ',
                create_numeric_variable_parameter_input(
                    input_id,
                    value = var.raw_parameters[0], # pyright: ignore[reportArgumentType]
                    placeholder = var.name
                ),
            ])
        ]
    else:
        content = [
            html.Span(
                create_numeric_variable_parameter_input(
                    input_id,
                    value = var.raw_parameters[0], # pyright: ignore[reportArgumentType]
                    placeholder = var.name
                ),
            )
        ]

    button_container_children = [
        dbc.Button(
            'Plot',
            color = 'primary',
            id = {
                'type': 'btn-action-optim-create-marginalplot', 'varid': f'{section}.{var.interface_key}.{var.interface_subindex}'
            },
            # id = {
            #     'type': 'action-button', 'purpose': 'request-process',
            #     'supersection': 'optim', 'section': 'tabledraw',
            #     'key': 'table_optim_metamodel', 'subindex': f'{section}.{var.interface_key}.{var.interface_subindex}',
            #     #'type': 'optim-marginal-plot-button',
            # },
            title = 'Plot marginal statistic',
            disabled = False
        ) # pyright: ignore[reportCallIssue]
    ]

    return [
        html.Div(
            [
                html.H4(label),
                html.Div(content, className = 'optim-configuration-summaryinfo')        
            ],
            className = 'configuration-header-title-container'
        ),
        html.Div(
            button_container_children,
            className = 'configuration-header-button-container'
        )
    ]

def create_positive_toggle(var):
    toggleid = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'input-toggle',
        supersection = 'optim',
        purpose = 'variable-positive',
    )

    return html.Span(
        [
            'Positive:',
            daq.ToggleSwitch(
                className = 'optim-opt-toggle',
                size = 25,
                value = False,
                id = toggleid.as_dict(),
            )
        ],
        className = 'optim-toggle-row',
    )

def create_bounded_toggle(var):
    toggleid = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'input-toggle',
        supersection = 'optim',
        purpose = 'variable-bounded',
    )
    
    return html.Span(
        [
            'Bounded:',
            daq.ToggleSwitch(
                className = 'optim-opt-toggle',
                size = 25,
                value = False,
                id = toggleid.as_dict(),
            )
        ],
        className = 'optim-toggle-row',
    )

def create_optim_bound_inputs(var: variable.ScalarVariable):
    variable_id_lower = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'single-input-config',
        supersection = 'optim',
        purpose = 'bound-lower'
    )
    variable_id_upper = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'single-input-config',
        supersection = 'optim',
        purpose = 'bound-upper'
    )
    variable_id_plotintervals = VariableInstanceParameterComponentID.from_variable(
        var,
        type = 'single-input-config',
        supersection = 'optim',
        purpose = 'plot-intervals',
    )
    
    return [
        dbc.InputGroup([
            dbc.InputGroupText('Lower bound:'), # pyright: ignore[reportCallIssue]
            create_numeric_variable_parameter_input(
                variable_id_lower,
                value = var.interface_min,
            ),
        ]),
        dbc.InputGroup([
            dbc.InputGroupText('Upper bound:'), # pyright: ignore[reportCallIssue]
            create_numeric_variable_parameter_input(
                variable_id_upper,
                value = var.interface_max,
            ),
        ]),
        dbc.InputGroup([
            dbc.InputGroupText('N plot:'), # pyright: ignore[reportCallIssue]
            create_numeric_variable_parameter_input(
                variable_id_plotintervals,
                value = 10,
                step = 1,
            ),
        ])
    ]

def create_optim_input(
    var: variable.NumericScalarVariable,
):
    return compose_optim_input(
        create_optim_header(var),
        #create_positive_toggle(var),
        #create_bounded_toggle(var),
        create_optim_bound_inputs(var),
        var
    )