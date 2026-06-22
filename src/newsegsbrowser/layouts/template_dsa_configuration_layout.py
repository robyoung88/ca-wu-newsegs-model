"""
Functions for creating a deterministic sensitivity analysis layout
"""
import os
import json
from typing import cast

from dash import html
import dash_bootstrap_components as dbc

from newsegsbrowser import STATICDATA
from newsegsbrowser.layouts import navigation
from newsegsbrowser.layouts.common import NULL_LAYOUT
from newsegsbrowser import variable_dash_component as var_dc
from newsegsvariable import variable

def create_dsa_header():
    return html.Div([
        dbc.Row([
            dbc.Col(
                html.H1(
                    [
                        'Deterministic Sensitivity Analysis',
                        html.Br(),
                        html.Span('Site: '),
                        html.Span(id = {'type': 'generic_text', 'section': 'any', 'key': 'site-name'}),
                    ]
                )
            )
        ]),
        dbc.Row([
            dbc.Col([
                html.H2(
                    [
                        html.Span('Configuration: '),
                        html.Span(id = {'type': 'generic_text', 'section': 'any', 'key': 'configuration-name'})
                    ]
                )
            ])
        ])
    ])

def create_dsa_configuration_editor(model_type: str | None = None):
    dsa_config_inputs = []
    if model_type is None:
        pass
    else:
        match model_type:
            case 'sprake':
                with open(os.path.join(STATICDATA, 'sprake-variable-config-novalues.json')) as f:
                    var_conf_list = json.load(f)
                variables =  [variable.Variable(**x) for x in var_conf_list]

                for var in variables:
                    if var.dsa_selectable:
                        if var.unit != '':
                            lbl = f'{var.name} ({var.unit})'
                        else:
                            lbl = f'{var.name}'
                        match var.distribution.distribution:
                            case 'constant':
                                is_scalar = True,
                                creation_func = var_dc.create_dsa_input_scalar_constant
                            case 'normal':
                                is_scalar = True,
                                creation_func = var_dc.create_dsa_input_scalar_normal
                            case 'beta':
                                is_scalar = True,
                                creation_func = var_dc.create_dsa_input_scalar_beta
                            case 'gamma':
                                is_scalar = True,
                                creation_func = var_dc.create_dsa_input_scalar_gamma
                            case _:
                                raise ValueError(f'Distribution {var.distribution.distribution} not currently supported')
                        
                        if is_scalar:
                            var = cast(variable.ScalarVariable, var)
                            if not var.interface_section:
                                dsa_config_inputs.append(
                                    creation_func(
                                        lbl, 
                                        'dsa-input-model-config',
                                        var.interface_key),
                                )
                            else:
                                dsa_config_inputs.append(
                                    creation_func(
                                        lbl, 
                                        'dsa-input-model-config',
                                        var.interface_key,
                                        section = var.interface_section),
                                )

    return dbc.Col([
        html.Div([
            html.H2(
                'DSA Configuration',
                style = {'display': 'inline-flex',
                         'margin-right': '20px'}
            ),
            dbc.Button('Run DSA'),
            ],
            style = {'vertical-align': 'baseline'}
            ),
        html.Div(
            dsa_config_inputs,
            #var_dc.create_dsa_input_scalar_constant('Wind Capacity (kW rated)', 'input-model-config', 'wind_capacity', section = 'gen_input'),
            #var_dc.create_dsa_input_scalar_constant('PV Capacity (kW rated)', 'input-model-config', 'pv_capacity', section = 'gen_input'),
            #var_dc.create_dsa_input_vector_mvn('Wind speed Weibull parameters', 'input-model-config', 'wind_speed_weibull', section = 'gen_input'),
            #var_dc.create_dsa_input_scalar_normal('Solar insolation multiplier', 'input-model-config', 'ghi_multiplier', section = 'gen_input'),
            #var_dc.create_dsa_input_scalar_constant('Storage Capacity (kWh)', 'input-model-config', 'stor_capacity', section = 'stor_input'),
            #var_dc.create_dsa_input_scalar_normal('HLP (W/m²/K)', 'input-model-config', 'hlp', section = 'bc_input'),
            #var_dc.create_dsa_input_scalar_constant('No. of households', 'input-model-config', 'n_units', section = 'bc_input'),
            #var_dc.create_dsa_input_scalar_normal('Ref. hot water demand (kWh/day/household)', 'input-model-config', 'ref_demand_dhw', section = 'bc_input'),
            #var_dc.create_dsa_input_scalar_normal('Seasonal variation (%)', 'input-model-config', 'variation_dhw', section = 'bc_input'),
            #var_dc.create_dsa_input_scalar_normal('High-efficiency appliances consumption reduction (fraction)', 'input-model-config', 'variation_dhw', section = 'dc_input'),
            #var_dc.create_dsa_input_scalar_normal('EVs per household (n)','input-model-config', 'ev_per_houshold', section = 'dc_input'),
            #var_dc.create_dsa_input_scalar_gamma('Wind Capex (£/kW)', 'input-finance-config', 'wind_capex', section = 'unit_costs'),
            #var_dc.create_dsa_input_scalar_gamma('Wind Ongoing (£/kW/yr)', 'input-finance-config', 'wind_ongoing', section = 'unit_costs'),
            #var_dc.create_dsa_input_scalar_gamma('Solar PV Capex (£/kWp)', 'input-finance-config', 'wind_capex', section = 'unit_costs'),
            #var_dc.create_dsa_input_scalar_gamma('Solar PV Ongoing (£/kWp/yr)', 'input-finance-config', 'wind_ongoing', section = 'unit_costs'),
            #var_dc.create_dsa_input_scalar_gamma('BESS Capex (£/kWph)', 'input-finance-config', 'wind_capex', section = 'unit_costs'),
            #var_dc.create_dsa_input_scalar_gamma('BESS Ongoing (£/kWp/yr)', 'input-finance-config', 'wind_ongoing', section = 'unit_costs'),
            #var_dc.create_dsa_input_scalar_gamma('Household standing charge (£/household/day)', 'input-finance-config', 'wind_ongoing', section = 'unit_costs'),
            #var_dc.create_dsa_input_scalar_gamma('Household per unit charge (£/kWh)', 'input-finance-config', 'wind_ongoing', section = 'unit_costs'),
            #var_dc.create_dsa_input_scalar_gamma('Export sales price (£/kWh)', 'input-finance-config', 'wind_ongoing', section = 'unit_costs'),
            #var_dc.create_dsa_input_scalar_gamma('Fixed costs for backup (£/site/day)', 'input-finance-config', 'wind_ongoing', section = 'unit_costs'),
            #var_dc.create_dsa_input_scalar_gamma('Per-unit costs for backup (£/kWh)', 'input-finance-config', 'wind_ongoing', section = 'unit_costs'),
        
        id = 'dsa_config_element_container'
        )
    ])



DEFAULT_LAYOUT_DSA = {
    'layout_navigation': navigation.create_navigator_buttons_default,
    'width_navigation': 1,
    'layout_head': create_dsa_header,
    'width_head': 11,

}

def create_dsa_layout(*args, **kwargs):
    config_dict = DEFAULT_LAYOUT_DSA.copy()
    config_dict.update(kwargs)

    header = dbc.Row([
        dbc.Col(
            html.Div(
                config_dict['layout_navigation'](config_dict.get('selected_model'))
            ),
            class_name = 'newsegs-navbar-vertical collapsed',
            width = config_dict['width_navigation'],
        ),
        dbc.Col(
            config_dict['layout_head'](),
            width = config_dict['width_head']
        )
    ])

    dsa_config = create_dsa_configuration_editor(kwargs.get('model_type'))


    

    return dbc.Container(
        html.Div(
            [
                header,
                html.Hr(),
                dbc.Row(
                    dsa_config
                ),
            ],
            
            
            id = 'main-content-pane'
        ),
        fluid = True,
        id = 'app-layout-wrapper'
    )