"""
Callbacks to populate input containers when the project or active metamodel changes.
"""

import json
import time
from typing import Any, Mapping, cast

from dash import ALL, MATCH, Input, Output, State, no_update
from dash import ctx
from dash.exceptions import PreventUpdate
import numpy as np

from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.components.constants import CONFIGURATION_UPDATE_TRIGGER_ID, VARIABLE_PARAMETER_KEYS
from newsegsmodelapp.components.get_focussed_metamodel import get_focussed_metamodel
from newsegsmodelapp.components.input_components import get_variable_sharing_status
from newsegsmodelapp.components.variable_dash_component.vdc import create_dsa_bounds_inputs_scalar
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelapp.registers import get_feedback_graph_artist, get_input_container_content_creator, get_input_section_header_content_creator, get_single_input_header_content_creator
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import make_varid
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsvariable import variable
from newsegsmodelapp.registers import get_input_handler

def add_input_container_callbacks(app: NewsegsDash) -> NewsegsDash:
    """
    Callbacks to populate input containers.

    An input container is identified by:
    {'type': 'input-container', 'supersection': 'XXX', 'section': 'XXX'}
    """

    @app.callback(
        Output({'type': 'input-container', 'supersection': MATCH, 'section': MATCH}, 'children'),

        Input('layout-update-trigger', 'data'),
        Input('active-project-id', 'data'),
        State('app-state', 'data'),

        State({'type': 'input-container', 'supersection': MATCH, 'section': MATCH}, 'id'),
        prevent_initial_call = True
    )
    def update_input_container_contents(
        layout_update_trigger,
        active_project_id,
        app_state,
        container_id
    ):
        if active_project_id is None:
            raise PreventUpdate
        trig = ctx.triggered_id
        if isinstance(trig, Mapping) and trig.get('type') == 'input-group-config-update-trigger':
            trig_val = callback_utils.get_triggered_value()
            if isinstance(trig_val, int):
                # Standard update - do nothing.
                raise PreventUpdate
                        
        app_state = json.loads(app_state) if app_state else {}
        
        input_supersection = container_id.get('supersection')
        input_section = container_id.get('section')
        selected_model = app_state.get('selected_model', 'default')

        if not input_supersection or not input_section:
            raise PreventUpdate

        try:
            content_creator = get_input_container_content_creator(
                input_supersection, input_section, selected_model
            )
        except KeyError as e:
            print('Content creator not found for ', str(container_id))
            print(e)
            return []

        return content_creator(active_project_id, app.project_provider)

    @app.callback(
        Output({'type': 'input-section-header', 'supersection': MATCH, 'section': MATCH}, 'children'),

        Input({'type': 'input-group-config-update-trigger', 
                       'supersection': MATCH, 'purpose': ALL,
                        'section': MATCH, 'key': ALL, 'subindex': ALL,
                        'parameter_index': ALL, 'vector_location': ALL}, 'data'),
        Input(CONFIGURATION_UPDATE_TRIGGER_ID, 'data'),
        Input('active-project-id', 'data'),
        State('app-state', 'data'),

        State({'type': 'input-container', 'supersection': MATCH, 'section': MATCH}, 'id'),
    )
    def update_input_section_header_contents(
        input_group_triggers,
        configuration_update_trigger,
        active_project_id,
        app_state,
        container_id,
    ):
        if active_project_id is None:
            raise PreventUpdate
        app_state = json.loads(app_state) if app_state else {}
                
        supersection = container_id.get('supersection')
        section = container_id.get('section')
        selected_model = app_state.get('selected_model', 'default')

        if not supersection or not section:
            raise PreventUpdate

        try:
            content_creator = get_input_section_header_content_creator(
                supersection, section, selected_model
            )
        except KeyError as e:
            print('Header creator not found for ', str(container_id))
            print(e)
            return []

        return content_creator(active_project_id, app.project_provider)

    @app.callback(
        Output({
            'type': 'single-input-config', 
            'supersection': ALL, 'purpose': ALL,
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL,
        }, 'value'),
        Output({
            'type': 'single-input-header', 
            'supersection': ALL, 'purpose': ALL,
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL,
        }, 'children'),
        Output({
            'type': 'input-group-config-update-trigger', 
            'supersection': ALL, 'purpose': ALL,
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL,
        }, 'data'),

        Input({
            'type': 'single-input-config', 
            'supersection': ALL, 'purpose': ALL,
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL,
        }, 'value'),
        Input({
            'type': 'dropdown',
            'supersection': ALL, 'purpose': ALL,
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL,
        }, 'value'),
        Input({
            'type': 'toggle',
            'supersection': ALL, 'purpose': ALL,
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL,
        }, 'value'),
        Input({
            'type': 'action-button',
            'supersection': ALL, 'purpose': ALL,
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL,
        }, 'n_clicks'),

        State({
            'type': 'single-input-config', 
            'supersection': ALL, 'purpose': ALL,
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL,
        }, 'id'),
        State({
            'type': 'single-input-header', 
            'supersection': ALL, 'purpose': ALL,
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL,
        }, 'id'),
        State({
            'type': 'input-group-config-update-trigger', 
            'supersection': ALL, 'purpose': ALL,
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL,
        }, 'id'),

        State('active-project-id', 'data'),
        State('app-state', 'data'),

        prevent_initial_call = True
    )
    def react_to_input_change(
        changed_input_values,
        changed_dropdown_values,
        changed_toggle_values,
        changed_action_button_values,
        input_ids,
        header_ids,
        trigger_ids,

        active_project_id,
        app_state
    ):
        
        print('Triggering object was ', ctx.triggered_id, type(ctx.triggered_id))
        print('Header ids are ', header_ids)
        print('Trigger ids are ', trigger_ids)
        print('Updated value is ', callback_utils.get_triggered_value())

        # Primary dispatch is on the purpose of the input
        trigger_id = ctx.triggered_id
        if trigger_id is None or active_project_id is None:
            raise PreventUpdate

        input_returns: list[Any] = [no_update] * len(input_ids)
        header_returns: list[Any] = [no_update] * len(header_ids)
        trigger_returns: list[Any] = [no_update] * len(trigger_ids)

        now = time.time_ns()
        
        match trigger_id['purpose']:
            case 'bound-lower' | 'bound-upper':
                match trigger_id['supersection']:
                    case 'dsa':
                        new_val = callback_utils.get_triggered_value()
                        proj = app.project_provider.get_project(active_project_id)
                        mm = proj.get_focussed_metamodel()
                        varid =  make_varid(**trigger_id)
                        var = mm.variables.get(varid)
                        if not var:
                            raise PreventUpdate
                        dsa_changed = False
                        if trigger_id['purpose'] == 'bound-lower':
                            if not new_val == var.dsa_lower:
                                var.dsa_lower = new_val
                                dsa_changed = True
                        else:
                            if not new_val == var.dsa_upper:
                                var.dsa_upper = new_val
                                dsa_changed = True

                        if dsa_changed:
                            # Update headers
                            for idx, id in enumerate(header_ids):
                                try:
                                    content_creator = get_single_input_header_content_creator(
                                        id['supersection'], id['section'], mm.model.model_type
                                    )
                                except KeyError:
                                    content_creator = None
                                if content_creator:
                                    varid =  make_varid(**trigger_id)
                                    header_returns[idx] = content_creator(varid, mm)

                            # Update triggers
                            for idx, id in enumerate(trigger_ids):
                                match id['supersection']:
                                    case 'dsa':
                                        trigger_returns[idx] = now

                            # Sync project to store
                            app.project_provider.upsert_component(proj)

                    case 'optim':
                        # Only need to pick up the bounds values when we perform the optimisation.
                        pass

            case 'dsaboundtype':
                new_val = callback_utils.get_triggered_value()
                proj = app.project_provider.get_project(active_project_id)
                mm = proj.get_focussed_metamodel()
                varid =  make_varid(**trigger_id)
                var = mm.variables.get(varid)
                if not var or new_val == var.dsa_bounds_type:
                    raise PreventUpdate

                var.dsa_bounds_type = new_val
                dsa_lower, dsa_upper = var.distribution.dsa_auto_values(var)
                var.dsa_lower = dsa_lower
                var.dsa_upper = dsa_upper

                # Update inputs
                for idx, id in enumerate(input_ids):
                    if id['purpose'] == 'bound-lower':
                        input_returns[idx] = dsa_lower
                    if id['purpose'] == 'bound-upper':
                        input_returns[idx] = dsa_upper

                # Update headers
                for idx, id in enumerate(header_ids):
                    try:
                        content_creator = get_single_input_header_content_creator(
                            id['supersection'], id['section'], mm.model.model_type
                        )
                    except KeyError:
                        content_creator = None
                    if content_creator:
                        varid =  make_varid(**trigger_id)
                        header_returns[idx] = content_creator(varid, mm)
                
                # Update triggers with a dictionary, not an integer
                trig_val = json.dumps({
                    'message': 'dsa_bounds_modified',
                    'time': now
                })
                for idx, id in enumerate(trigger_ids):
                    match id['supersection']:
                        case 'dsa':
                            trigger_returns[idx] = trig_val

                 # Sync project to store
                app.project_provider.upsert_component(proj)

            case 'dsa-active':
                new_val = callback_utils.get_triggered_value()
                proj = app.project_provider.get_project(active_project_id)
                mm = proj.get_focussed_metamodel()
                varid =  make_varid(**trigger_id)
                var = mm.variables.get(varid)
                if not var or new_val == var.dsa_selected:
                    raise PreventUpdate

                var.dsa_selected = new_val

                # Update triggers with a dictionary, not an integer
                trig_val = json.dumps({
                    'message': 'dsa_selection_status_modified',
                    'time': now
                })
                for idx, id in enumerate(trigger_ids):
                    match id['supersection']:
                        case 'dsa':
                            trigger_returns[idx] = trig_val

                # Sync project to store
                app.project_provider.upsert_component(proj)

            case _:
                try:
                    handler = get_input_handler(trigger_id['purpose'], trigger_id['type'], json.loads(app_state).get('selected_model', 'default'))
                except KeyError:
                    print(f'No handlers for purpose {trigger_id["purpose"]}')
                    raise PreventUpdate
                if handler:
                    return handler(
                        trigger_id,
                        input_ids,
                        changed_input_values,
                        header_ids,
                        trigger_ids,
                        active_project_id,
                        app.project_provider
                    )
                else:
                    print(f'No handlers for purpose {trigger_id["purpose"]}')
                    raise PreventUpdate

        return (input_returns, header_returns, trigger_returns)

    @app.callback(
        Output({
            'type': 'input-component', 
            'supersection': 'dsa', 'purpose': 'bounds-container',
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL},
            'children'
        ),
        Output({
            'type': 'input-component', 
            'supersection': 'dsa', 'purpose': 'input-group-container',
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL},
            'className'
        ),

        Input({
            'type': 'input-group-config-update-trigger', 
            'supersection': 'dsa', 'purpose': 'trigger',
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL},
            'data'
        ),

        Input('active-project-id', 'data'),
        State('app-state', 'data'),
        State({
            'type': 'input-component', 
            'supersection': 'dsa', 'purpose': 'bounds-container',
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL},
            'id'
        ),
    )
    def update_dsa_input_contents(
        input_group_triggers,
        active_project_id,
        app_state,
        container_ids
    ):
        if not len(container_ids):
            raise PreventUpdate
        mm = get_focussed_metamodel(active_project_id, app.project_provider)

        varid = make_varid(**container_ids[0])
        var = mm.variables.get(varid)
        if not var:
            raise PreventUpdate
        if not isinstance(var, variable.NumericScalarVariable):
            raise PreventUpdate
        bounds_input = create_dsa_bounds_inputs_scalar(var.dsa_bounds_type, var)

        if var.dsa_selected:
            cn = 'dsa-input-single-value-block'
        else:
            cn = 'dsa-input-single-value-block deselected'

        return (
            [bounds_input] * len(container_ids),
            [cn] * len(container_ids)
        )

     # Updates to inputs based on config
    @app.callback(
        Output('site-location', 'data', allow_duplicate = True),
        
        Input('active-project-id', 'data'),
        prevent_initial_call = True
    )
    def sync_loc_inputs_to_store(
        active_project_id
    ):
        mm = get_focussed_metamodel(active_project_id, app.project_provider)
        
        loc_input = {
            'lat': mm.model.location.lat,
            'lon': mm.model.location.lon,
            'name': mm.model.location.name
        }
        return json.dumps(loc_input)

    @app.callback(
        Output({'type': 'feedback-graph', 'section': ALL, 'key': ALL}, 'figure'),

        Input({'type': 'input-group-config-update-trigger', 
                'supersection': ALL, 'purpose': ALL,
                'section': ALL, 'key': ALL, 'subindex': ALL,
                'parameter_index': ALL, 'vector_location': ALL}, 
                'data'),

        State({'type': 'feedback-graph', 'section': ALL, 'key': ALL}, 'id'),
        State('active-project-id', 'data'),
        State('app-state', 'data'),

        prevent_initial_call = True
    )
    def update_feedback_graphs(
        configuration_update_trigger,
        figure_ids,
        active_project_id,
        app_state
    ):
        app_state = json.loads(app_state) if app_state else {}
        selected_model = app_state.get('selected_model', 'default')

        figure_returns: list[Any] = [no_update] * len(figure_ids)

        for idx, id in enumerate(figure_ids):
            try:
                artist = get_feedback_graph_artist(id['key'], selected_model)
            except KeyError:
                artist = None
            if artist:
                figure_returns[idx] = artist(active_project_id, app.project_provider)

        return figure_returns        


    @app.callback(
        Output({
            'type': 'action-button', 
            'supersection': MATCH, 'purpose': 'variable-status-toggle',
            'section': MATCH, 'key': MATCH, 'subindex': ALL,
            'parameter_index': ALL, 'vector_location': ALL
        }, 'children'),
        Output({
            'type': 'action-button', 
            'supersection': MATCH, 'purpose': 'variable-status-toggle',
            'section': MATCH, 'key': MATCH, 'subindex': ALL,
            'parameter_index': ALL, 'vector_location': ALL
        }, 'color'),

        Input({
            'type': 'input-group-config-update-trigger', 
            'supersection': MATCH, 'purpose': 'variable-status-trigger',
            'section': MATCH, 'key': MATCH, 'subindex': ALL,
            'parameter_index': ALL, 'vector_location': ALL
        }, 'data'),

        State({
            'type': 'action-button', 
            'supersection': MATCH, 'purpose': 'variable-status-toggle',
            'section': MATCH, 'key': MATCH, 'subindex': ALL,
            'parameter_index': ALL, 'vector_location': ALL
        }, 'id'),

        State('active-project-id', 'data'),
        prevent_initial_call = True,
    )
    def update_variable_status_badge(
        trigger_data,
        button_ids,
        active_project_id
    ):
        trigger_id = ctx.triggered_id
        if trigger_id is None or active_project_id is None:
            raise PreventUpdate

        triggered_id = ctx.triggered_id
        proj = app.project_provider.get_project(active_project_id)
        mm = proj.get_focussed_metamodel()
        varid = make_varid(**triggered_id) # pyright: ignore[reportCallIssue]
        contents, colour = get_variable_sharing_status(proj, mm, varid)
        return [contents] * len(button_ids), [colour] * len(button_ids)
        
    return app

    
