"""
Layout and callbacks for interfacing with Variables
"""
from typing import Any, Sequence
from collections import OrderedDict

from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_daq as daq

from newsegsvariable import variable
import newsegsbrowser.common as browser

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
        return dbc.Input(type = 'number', debounce = True, placeholder = placeholder)

    def make_inputgroup(label: str, placeholder: Any):
        return dbc.InputGroup([
            dbc.InputGroupText(label+':'),
            make_input(placeholder)
        ])
    
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
    

def create_dsa_bounds_inputs_scalar(
    bounds_type: variable.DSA_BOUNDS_TYPE,
    var: variable.ScalarVariable,
):
    type_id_lower = f'input-dsabound-lower'
    type_id_upper = f'input-dsabound-upper'
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
                    dbc.InputGroupText('Lower:'),
                    browser.create_numeric_input_compound_key(
                        type_id_lower,
                        var.interface_key,
                        section = var.interface_section,
                        subindex = var.interface_subindex,
                        value = var.dsa_lower,
                        step = step_size
                    )
                ]
                ),
                dbc.InputGroup([
                    dbc.InputGroupText('Upper:'),
                    browser.create_numeric_input_compound_key(
                        type_id_upper,
                        var.interface_key,
                        section = var.interface_section,
                        subindex = var.interface_subindex,
                        value = var.dsa_upper,
                        step = step_size
                    )
                ]
                ),
            ]
        case 'interval':
            return [
                dbc.InputGroup([
                    dbc.InputGroupText('Confidence:'),
                    browser.create_numeric_input_compound_key(
                        type_id_lower,
                        var.interface_key,
                        section = var.interface_section,
                        subindex = var.interface_subindex,
                        value = var.dsa_lower
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
        return dbc.Input(type = 'number', debounce = True, placeholder = placeholder)
    
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
    type_id = f'dropdown-dsaboundtype'
    section = var.interface_section
    if section is None:
        section = 'None'
    id_ = {
        'type': type_id,
        'section': section,
        'key': var.interface_key,
        'subindex': var.interface_subindex
    }
    return [
        dcc.Dropdown(
            permitted_dsa_bounds,
            selected_bound,
            id = id_,
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
    section = var.interface_section
    if section is None:
        section = 'None'
    
    header_id = {
        'type': 'dsa-input-header',
        'section': section,
        'key': var.interface_key,
        'subindex': var.interface_subindex
    }

    bounds_id = {
        'type': 'dsa-bounds-inputcontainer',
        'section': section,
        'key': var.interface_key,
        'subindex': var.interface_subindex
    }


    return html.Div([
        daq.ToggleSwitch(
            #vertical = True,
            className = 'dsa-toggle',
            size = 30,
            value = var.dsa_selected
        ),
        html.Details([
            html.Summary(
                header_component,
                className='dsa-configuration-summary',
                id = header_id
            ),
            html.Div((
                parameter_component
                + dsa_bound_type_selector
                + [
                    html.Span(
                        dsa_bound_component,
                        id = bounds_id
                    )
                ]
            ))
        ],
        ),
    ],
    className='dsa-input-single-value-block',
    )

def create_dsa_header(
    var: variable.ScalarVariable,
):
    if var.distribution.distribution == 'constant':
        fmt = _autoformat
    else:
        fmt = var.value_formatter
    label = f'{var.label} ({var.unit})'
    type_id = f'input-{var.configuration_type}-config'

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
    type_id = f'input-{var.configuration_type}-config'
    return compose_dsa_input(
        create_dsa_header(var),
        [
            dbc.InputGroup([
                dbc.InputGroupText('Value:'),
                browser.create_numeric_input_compound_key(
                    type_id,
                    var.interface_key,
                    section = var.interface_section,
                    subindex = var.interface_subindex,
                    value = var.get_deterministic_value(), # pyright: ignore[reportArgumentType]
                    min = var.interface_min,
                    max = var.interface_max,
                    step = var.interface_step if var.interface_step else 1
                ),
            ])
        ],
        create_dsa_bound_type_selector(
            ['absolute', 'relative', 'offset'],
            var.dsa_bounds_type,
            var,
        ),
        create_dsa_bounds_inputs_scalar(
            var.dsa_bounds_type,
            var,
        ),
        var
    )


# A form element for a normally distributed variable
# e.g. a scaling factor for expected annual insolation
def create_dsa_input_scalar_normal(
    var: variable.NumericScalarVariable,
):
    type_id = f'input-{var.configuration_type}-config'
    return compose_dsa_input(
        create_dsa_header(var),
        [
            dbc.InputGroup([
                        dbc.InputGroupText('Mean:'),
                        browser.create_numeric_input_compound_key(
                            type_id,
                            var.interface_key,
                            section = var.interface_section,
                            subindex = var.interface_subindex,
                            value = var._raw_parameters[0], # pyright: ignore[reportArgumentType]
                            placeholder = 'Mean',
                            min = var.interface_min,
                            max = var.interface_max,
                            step = var.interface_step if var.interface_step else 1
                        )
                    ]
                    ),
                    dbc.InputGroup([
                        dbc.InputGroupText('SD:'),
                        browser.create_numeric_input_compound_key(
                            type_id,
                            var.interface_key,
                            section = var.interface_section,
                            subindex = var.interface_subindex,
                            parameter_index = 1,
                            value = var._raw_parameters[1], # pyright: ignore[reportArgumentType]
                            placeholder = 'SD',
                            step = var.interface_step/10 if var.interface_step else 1
                        )
                    ]
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
    type_id = f'input-{var.configuration_type}-config'
    return compose_dsa_input(
        create_dsa_header(var),
        [
            dbc.InputGroup([
                        dbc.InputGroupText('Mean:'),
                       browser.create_numeric_input_compound_key(
                            type_id,
                            var.interface_key,
                            section = var.interface_section,
                            subindex = var.interface_subindex,
                            value = var._raw_parameters[0], # pyright: ignore[reportArgumentType]
                            placeholder = 'Mean',
                            min = var.interface_min,
                            max = var.interface_max,
                            step = var.interface_step if var.interface_step else 1
                        )
                    ]
                    ),
                    dbc.InputGroup([
                        dbc.InputGroupText('SD:'),
                        browser.create_numeric_input_compound_key(
                            type_id,
                            var.interface_key,
                            section = var.interface_section,
                            subindex = var.interface_subindex,
                            parameter_index = 1,
                            value = var._raw_parameters[1], # pyright: ignore[reportArgumentType]
                            placeholder = 'SD',
                            step = var.interface_step/10 if var.interface_step else 1
                        )
                    ]
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
            dbc.InputGroup([
                        dbc.InputGroupText('Mean:'),
                        browser.create_numeric_input_compound_key(
                            type_id,
                            var.interface_key,
                            section = var.interface_section,
                            subindex = var.interface_subindex,
                            value = var._raw_parameters[0], # pyright: ignore[reportArgumentType]
                            placeholder = 'Mean',
                            min = var.interface_min,
                            max = var.interface_max,
                            step = var.interface_step if var.interface_step else 1
                        )
                    ]
                    ),
                    dbc.InputGroup([
                        dbc.InputGroupText('SD:'),
                        browser.create_numeric_input_compound_key(
                            type_id,
                            var.interface_key,
                            section = var.interface_section,
                            subindex = var.interface_subindex,
                            parameter_index = 1,
                            value = var._raw_parameters[1], # pyright: ignore[reportArgumentType]
                            placeholder = 'SD',
                            step = var.interface_step/10 if var.interface_step else 1
                        )
                    ]
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

def create_dsa_input_vector_mvn(
    var: variable.NumericVectorVariable,
):
    fmt = var.value_formatter
    label = f'{var.label} ({var.unit})'
    type_id = f'input-{var.configuration_type}-config'
    return compose_dsa_input(
        create_dsa_input_vector_numeric_header(label, type_id, key, section),
        create_dsa_input_vector_parameter_input(OrderedDict(mean = ['shape', 'scale'], vcv = ['covariance']), ('vector', 'matrix'), type_id, key, section),
        create_dsa_bound_type_selector(['absolute', 'relative', 'offset', 'interval'],'interval', type_id, key, section),
        create_dsa_bounds_input_vector('relative', type_id, key, section),
        var
    )
