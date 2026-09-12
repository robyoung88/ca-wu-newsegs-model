"""
Callbacks to populate input containers when the project or active metamodel changes.
"""

import json
import time
from typing import Any, cast

from dash import ALL, MATCH, Input, Output, State, no_update
from dash import ctx
from dash.exceptions import PreventUpdate
import numpy as np

from newsegsmodelapp.components.constants import CONFIGURATION_UPDATE_TRIGGER_ID, VARIABLE_PARAMETER_KEYS
from newsegsmodelapp.components.get_focussed_metamodel import get_focussed_metamodel
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelapp.newsegsbrowser.common import get_triggered_value
from newsegsmodelapp.registers import get_feedback_graph_artist, get_input_container_content_creator, get_input_section_header_content_creator, get_single_input_header_content_creator
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import make_varid
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject

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
        print('update input has been fired for ', container_id)
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

        Input('active-project-id', 'data'),
        State('app-state', 'data'),

        prevent_initial_call = True
    )
    def react_to_input_change(
        changed_input_values,
        input_ids,
        header_ids,
        trigger_ids,

        active_project_id,
        app_state
    ):
        print('Responding to a change in input within group ', input_ids, type(input_ids[0]))
        print('Triggering object was ', ctx.triggered_id, type(ctx.triggered_id))
        print('Changed values are ', changed_input_values)
        print('Header ids are ', header_ids)
        print('Trigger ids are ', trigger_ids)
        print('Updated value is ', get_triggered_value())

        # Primary dispatch is on the purpose of the input
        trigger_id = ctx.triggered_id
        if trigger_id is None:
            raise PreventUpdate

        input_returns: list[Any] = [no_update] * len(input_ids)
        header_returns: list[Any] = [no_update] * len(header_ids)
        trigger_returns: list[Any] = [no_update] * len(trigger_ids)

        now = time.time_ns()
        
        match trigger_id['purpose']:
            case 'parameter':
                new_val = get_triggered_value()
                proj = cast(NewsegsProject, app.project_provider.get_component(active_project_id))
                mm = proj.get_focussed_metamodel()
                variable_keys = {k: trigger_id.get(k) for k in VARIABLE_PARAMETER_KEYS}
                
                update_ok, deterministic_changed, dsa_changed, psa_changed, raw_params = mm.update_variable_from_interface(
                    value = new_val, **variable_keys
                )

                # Feed back current parameters
                for idx, id in enumerate(input_ids):
                    if id['purpose'] == 'parameter':
                        pi = id['parameter_index']
                        new_param = raw_params[pi]
                        if not isinstance(new_param, np.ndarray):
                            input_returns[idx] = new_param
                        else:
                            vi = id['vector_location']
                            new_val = new_param.flat[vi]
                            input_returns[idx] = new_val

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
                        case 'deterministic':
                            if deterministic_changed:
                                trigger_returns[idx] = now
                        case 'dsa':
                            if dsa_changed:
                                trigger_returns[idx] = now
                        case 'psa':
                            if psa_changed:
                                trigger_returns[idx] = now

                # Sync project to store
                app.project_provider.upsert_component(proj)

                # TODO: Feed back to inputs if the update is not ok (set invalid)
            case 'bound-lower' | 'bound-upper':
                match trigger_id['supersection']:
                    case 'dsa':
                        new_val = get_triggered_value()
                        proj = cast(NewsegsProject, app.project_provider.get_component(active_project_id))
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
                            
            case _:
                print(f'No handlers for purpose {trigger_id["purpose"]}')

        return (input_returns, header_returns, trigger_returns)

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
    
    return app

    
