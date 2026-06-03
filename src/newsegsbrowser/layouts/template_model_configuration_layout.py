"""
Functions for creating a model configuration layout for an app.

Many of these functions require configured sub-functions to actually perform
the bespoke layout creation.
"""
from dash import dcc, html
import dash_bootstrap_components as dbc

from src.newsegsbrowser.layouts import navigation
from src.newsegsbrowser.layouts.inputs import maps
from src.newsegsbrowser.layouts.feedback import indicative_net_energy
from src.newsegsbrowser.layouts.common import NULL_LAYOUT

from src.newsegsbrowser.layouts.inputs import generation_input_sprake
from src.newsegsbrowser.layouts.inputs import storage_input_sprake
from src.newsegsbrowser.layouts.inputs import building_consumption_input_sprake
from src.newsegsbrowser.layouts.inputs import direct_consumption_input_sprake
from src.newsegsbrowser.layouts.inputs import model_settings_input_sprake
from src.newsegsbrowser.layouts.inputs import gen_cost_input_sprake
from src.newsegsbrowser.layouts.inputs import storage_cost_input_sprake
from src.newsegsbrowser.layouts.inputs import sales_input_sprake
from src.newsegsbrowser.layouts.inputs import import_cost_input_sprake
from src.newsegsbrowser.layouts.inputs import finance_settings_input_sprake

from src.newsegsbrowser.layouts.results import results_header
from src.newsegsbrowser.layouts.results import configuration_selector
from src.newsegsbrowser.postprocess.tables import results_tables_map
from src.newsegsbrowser.layouts.results import generation_results_sprake
from src.newsegsbrowser.layouts.results import storage_results_sprake
from src.newsegsbrowser.layouts.results import consumption_results_sprake
from src.newsegsbrowser.layouts.results import net_energy_results_sprake
from src.newsegsbrowser.layouts.results import economic_results_so_sprake

DEFAULT_LAYOUT_CONFIGURATION = {
    'layout_navigation': navigation.create_navigator_buttons_default,
    'width_navigation': 1,
    'layout_map': maps.create_site_selector_map,
    'width_map': 11,
    'layout_top_feedback': indicative_net_energy.create_indicative_net_energy_card,
    'width_top_feedback': 12,
    'layout_generation_input': generation_input_sprake.create_generation_input_card,
    'width_generation_input': 6,
    'layout_storage_input': storage_input_sprake.create_storage_input_card,
    'width_storage_input': 6,
    'layout_building_consumption_input': building_consumption_input_sprake.create_building_consumption_input_card,
    'width_building_consumption_input': 6,
    'layout_direct_consumption_input': direct_consumption_input_sprake.create_direct_consumption_input_card,
    'width_direct_consumption_input': 6,
    'layout_grid_input': NULL_LAYOUT,
    'width_grid_input': 12,
    'layout_model_settings_input': model_settings_input_sprake.create_model_settings_input_card,
    'width_model_settings_input': 12,
    'layout_generation_cost_input': gen_cost_input_sprake.create_gen_cost_input_card,
    'width_generation_cost_input': 6,
    'layout_storage_cost_input': storage_cost_input_sprake.create_storage_cost_input_card,
    'width_storage_cost_input': 6,
    'layout_sales_input': sales_input_sprake.create_sales_input_card,
    'width_sales_input': 6,
    'layout_import_cost_input': import_cost_input_sprake.create_import_cost_input_card,
    'width_import_cost_input': 6,
    'layout_finance_settings_input': finance_settings_input_sprake.create_finance_settings_input_card,
    'width_finance_settings_input': 12,

    'layout_results_header': results_header.create_results_header,
    'layout_configuration_selector': configuration_selector.create_configuration_selector,
    'results_table_functions': results_tables_map.SPRAKE_RESULT_TABLES,
    'layout_generation_results': generation_results_sprake.create_generation_results_card,
    'width_generation_results': 12,
    'layout_grid_results': NULL_LAYOUT,
    'width_grid_results': 12,
    'layout_storage_results': storage_results_sprake.create_storage_results_card,
    'width_storage_results': 12,
    'layout_consumption_results': consumption_results_sprake.create_consumption_results_card,
    'width_consumption_results': 12,
    'layout_net_results': net_energy_results_sprake.create_net_results_card,
    'width_net_results': 12,
    'layout_economic_so_results': economic_results_so_sprake.create_economic_results_so_card,
    'width_economic_so_results': 12,
}

def create_model_configuration_layout(*args, **kwargs):

    config_dict = DEFAULT_LAYOUT_CONFIGURATION.copy()
    config_dict.update(kwargs)
    
    header = [dbc.Row([
        dbc.Col(
            html.Div(
                config_dict['layout_navigation'](),
            ),
            class_name = 'newsegs-navbar-vertical collapsed',
            width = config_dict['width_navigation'],
            
        ),
        dbc.Col(
            config_dict['layout_map'](),
            width = config_dict['width_map']
        )
    ])]

    model_input_sections = []
    for sec in [
        'generation_input',
        'storage_input',
        'building_consumption_input',
        'direct_consumption_input',
        'grid_input'
    ]:
        model_input_sections.append(
            dbc.Col(
                config_dict[f'layout_{sec}'](),
                width = config_dict[f'width_{sec}']
            )
        )

    finance_input_sections = []
    for sec in [
        'generation_cost_input',
        'storage_cost_input',
        'sales_input',
        'import_cost_input',
        'finance_settings_input',
    ]:
        finance_input_sections.append(
            dbc.Col(
                config_dict[f'layout_{sec}'](),
                width = config_dict[f'width_{sec}']
            )
        )

    site_details = [
        dbc.Row(
            dbc.Col(
                config_dict['layout_top_feedback'](),
                width = config_dict['width_top_feedback']
            )
        ),

        dbc.Row(model_input_sections),
        
        html.Hr(),

        dbc.Row(finance_input_sections),
    ]

    results_table_functions = config_dict['results_table_functions']

    results_subsections = []
    for sec in [
        'generation_results',
        'grid_results',
        'storage_results',
        'consumption_results',
        'net_results',
        'economic_so_results'
    ]:
        results_subsections.append(
            dbc.Col(
                config_dict[f'layout_{sec}'](results_table_functions),
                width = config_dict[f'width_{sec}']
            )
        )

    results_section = [
        html.Div([
            dcc.Loading([
                config_dict['layout_results_header'](),
                html.Div([
                    config_dict['layout_configuration_selector'](),
                    dbc.Row(
                        results_subsections
                    )
                ],
                id = 'drawer-content',
                ),

                # Watched to trigger after the layout loads
                dcc.Store(id = 'firstload-config-watcher'),

                ##### Queues
                
                # A queue of actions performed by the user
                # Generally will hold changes to model and finance configurations
                # to enact.
                dcc.Store(id = 'queue-action-user'),
                # A pre-queue holds individual actions on the way to the queue
                # manager
                dcc.Store(id = 'prequeue-action-user', data = []),
                # A dispatch object holds actions that may be handled by the
                # dispatcher.
                dcc.Store(id = 'dispatchitem-action-user'),
                # An Interval element is necessary to trigger the queue until
                # it is cleared
                dcc.Interval(id = 'interval-action-user', interval = 1000, disabled = True),

                # A queue of model run requests
                # Will generally get added to when a configuration changes
                # but the running of the model is latched off
                dcc.Store(id = 'queue-model-run'),
                # A pre-queue to transfer model run requests to the queue
                # manager
                dcc.Store(id = 'prequeue-model-run'),
                # An Interval element to trigger the queue until it is cleared
                dcc.Interval(id = 'interval-model-run', interval = 1000, disabled = True),
                # A dispatch object holding id of a model permitted to run
                dcc.Store(id = 'dispatchitem-model-run'),
                # Trigger object for the model run
                dcc.Store(id = 'trigger-model-run'),
                # Trigger object for relocalising model after run
                dcc.Store(id = 'trigger-post-model-run'),
                # A store to trigger handling of model run completion
                dcc.Store(id = 'trigger-postprocess-model-run'),

                # A queue of finance run requests
                # A pre-queue to transfer finance run requests to the queue
                # manager
                dcc.Store(id = 'prequeue-finance-run'),
                # The queue to hold scheduled finance runs
                dcc.Store(id = 'queue-finance-run'),
                # An Interval to trigger the queue manager until queue is cleared
                dcc.Interval(id = 'interval-finance-run', interval = 1000, disabled = True),
                # A dispatch object holding id of a finance permitted to run
                dcc.Store(id = 'dispatchitem-finance-run'),
                # Trigger object for the finance run
                dcc.Store(id = 'trigger-finance-run'),
                # Trigger object for relocalising finance after run
                dcc.Store(id = 'trigger-post-finance-run'),
                # Trigger handling of finance run completion
                dcc.Store(id = 'trigger-postprocess-finance-run'),

                ##### Latches

                # A global switch to disable model runs
                dcc.Store(id = 'latch-model-run-global'),
                # A global switch to disable finance runs
                dcc.Store(id = 'latch-finance-run-global'),
                # A list of checked-out models whose configuration cannot be updated
                dcc.Store(id = 'latch-models-checkedout'),
                # A list of checked-out finances whose configuration cannot be updated
                dcc.Store(id = 'latch-finances-checkedout'),

                # A store of the available and active configurations
                # As a JSON list of the results of `compose_configuration`
                #dcc.Store(id = 'store-selected-configuration'),
                #dcc.Store(id = 'store-configurations'),

                # Stores for the -to-interface configurations of the models
                # and finances that are in the current session.
                # These should only really be necessary to draw from when
                # recreating a model after a migration
                dcc.Store(id = 'store-model-interface-configurations'),
                dcc.Store(id = 'store-finance-interface-configurations'),

                # Stores live data for moving around
                dcc.Store(id='model-config'),
                dcc.Store(id='finance-config'),

                # Triggers for result table updates after postprocessing
                dcc.Store(id='res-gen'),
                dcc.Store(id='res-stor'),
                dcc.Store(id='res-cons'),
                dcc.Store(id='res-net'),
                dcc.Store(id='res-finance-so-benefits'),
                dcc.Store(id='res-finance-so-costs'),
                dcc.Store(id='res-finance-so-value'),
            ],

            overlay_style = {
                'visibility': 'visible',
                'filter': 'blur(2px)',
                'display': 'block',
            },
            id = 'loading-results',
            parent_className = 'drawer-loading-container',

            )
        ],
        id = 'drawer-container'
        ),

        html.Div(
            id = 'post-drawer-attach',
            style = {'display': 'none'}
        ),   
    ]
    
    return dbc.Container(
        html.Div(
            (
                header
                + [html.Hr()]
                + site_details
                + [html.Hr()]
                + results_section
                + [html.Div(id='onload-div')] # To trigger first callback
            ),
            id = 'main-content-pane',
        ),
        fluid = False,
        id = 'app-layout-wrapper'
    )
    