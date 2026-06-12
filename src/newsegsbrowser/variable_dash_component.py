"""
Layout and callbacks for interfacing with Variables
"""
from typing import Any, Sequence
from collections import OrderedDict

from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_daq as daq

from src.newsegsbrowser import variable

def create_dsa_input_scalar_numeric_header(
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
                '100.0'
            ),
            html.Div([
                '[',
                html.Span(
                    '80.0'
                ),
                ',',
                html.Span(
                    '120.0'
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
    type_id: str,
    key: str,
    section: str | None = None,
    #var: variable.Variable
):
    match bounds_type:
        case 'absolute' | 'relative' | 'offset':
            return [
                dbc.InputGroup([
                    dbc.InputGroupText('Lower:'),
                    dbc.Input(
                        type = 'number',
                        debounce = True,
                        placeholder = 'Lower'
                    )
                ]
                ),
                dbc.InputGroup([
                    dbc.InputGroupText('Upper:'),
                    dbc.Input(
                        type = 'number',
                        debounce = True,
                        placeholder = 'Upper'
                    )
                ]
                ),
            ]
        case 'interval':
            return [
                dbc.InputGroup([
                    dbc.InputGroupText('Confidence:'),
                    dbc.Input(
                        type = 'number',
                        debounce = True
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
    type_id: str,
    key: str,
    section: str | None = None,
):
    return [
        dcc.Dropdown(
            permitted_dsa_bounds,
            selected_bound,
            searchable = False,
            clearable = False
        )
    ]

def compose_dsa_input(
    header_component,
    parameter_component,
    dsa_bound_type_selector,
    dsa_bound_component
):
    return html.Div([
        daq.ToggleSwitch(
            #vertical = True,
            className = 'dsa-toggle',
            size = 30
        ),
        html.Details([
            html.Summary(
                header_component,
                className='dsa-configuration-summary'
            ),
            html.Div((
                parameter_component 
                + dsa_bound_type_selector
                + dsa_bound_component
            ))
        ],
        ),
        

    ],
    className='dsa-input-single-value-block',
    )

def create_dsa_input_scalar_constant(
    label: str,
    type_id: str,
    key: str,
    section: str | None = None,
):
    return compose_dsa_input(
        create_dsa_input_scalar_numeric_header(label, type_id, key, section),
        [
            dbc.InputGroup([
                dbc.InputGroupText('Value:'),
                dbc.Input(type = 'number', debounce = True, placeholder = 'Value')
            ])
        ],
        create_dsa_bound_type_selector(['absolute', 'relative', 'offset'],'relative', type_id, key, section),
        create_dsa_bounds_inputs_scalar(
            'relative',
            type_id,
            key,
            section
        )
    )


# A form element for a normally distributed variable
# e.g. a scaling factor for expected annual insolation
def create_dsa_input_scalar_normal(
    label: str,
    type_id: str,
    key: str,
    section: str | None = None,
):
    return compose_dsa_input(
        create_dsa_input_scalar_numeric_header(label, type_id, key, section),
        [
            dbc.InputGroup([
                        dbc.InputGroupText('Mean:'),
                        dbc.Input(type = 'number', debounce = True, placeholder = 'Value')
                    ]
                    ),
                    dbc.InputGroup([
                        dbc.InputGroupText('SD:'),
                        dbc.Input(type = 'number', debounce = True, placeholder = 'SD')
                    ]
                    ),
        ],
        create_dsa_bound_type_selector(['absolute', 'relative', 'offset', 'interval'],'interval', type_id, key, section),
        create_dsa_bounds_inputs_scalar(
            'interval',
            type_id,
            key,
            section
        )
    )

def create_dsa_input_scalar_gamma(
    label: str,
    type_id: str,
    key: str,
    section: str | None = None,
):
    return compose_dsa_input(
        create_dsa_input_scalar_numeric_header(label, type_id, key, section),
        [
            dbc.InputGroup([
                        dbc.InputGroupText('Mean:'),
                        dbc.Input(type = 'number', debounce = True, placeholder = 'Value')
                    ]
                    ),
                    dbc.InputGroup([
                        dbc.InputGroupText('SD:'),
                        dbc.Input(type = 'number', debounce = True, placeholder = 'SD')
                    ]
                    ),
        ],
        create_dsa_bound_type_selector(['absolute', 'relative', 'offset', 'interval'],'interval', type_id, key, section),
        create_dsa_bounds_inputs_scalar(
            'interval',
            type_id,
            key,
            section
        )
    )

def create_dsa_input_vector_mvn(
    label: str,
    type_id: str,
    key: str,
    section: str | None = None,
):
    return compose_dsa_input(
        create_dsa_input_vector_numeric_header(label, type_id, key, section),
        create_dsa_input_vector_parameter_input(OrderedDict(mean = ['shape', 'scale'], vcv = ['covariance']), ('vector', 'matrix'), type_id, key, section),
        create_dsa_bound_type_selector(['absolute', 'relative', 'offset', 'interval'],'interval', type_id, key, section),
        create_dsa_bounds_input_vector('relative', type_id, key, section)
    )
