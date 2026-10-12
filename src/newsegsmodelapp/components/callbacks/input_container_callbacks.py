"""
Callbacks to populate input containers when the project or active metamodel changes.
"""

import json
import time
from typing import Any, cast

from dash import ALL, MATCH, Input, Output, State, no_update
from dash import ctx
from dash.exceptions import PreventUpdate

from newsegsmodelapp.backend.db import db
from newsegsmodelapp.backend.db.db_component_provider import CachedFromDatabaseNewsegsProjectProvider, FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.backend.db.db_variable_provider import CachedFromDatabaseVariableProvider
from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.components.constants import CONFIGURATION_UPDATE_TRIGGER_ID
from newsegsmodelapp.components.get_focussed_metamodel import get_focussed_metamodel
from newsegsmodelapp.components.input_components import get_variable_sharing_status
from newsegsmodelapp.components.variable_dash_component.vdc import create_dsa_bounds_inputs_scalar
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelapp.registers import get_feedback_graph_artist, get_input_container_content_creator, get_input_section_header_content_creator, get_single_input_header_content_creator
from newsegsmodelframework.newsegsmetamodel.lightweightnewsegsmetamodel import LightweightNewsegsMetaModel
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel, make_varid
from newsegsmodelframework.newsegsproject.lightweightnewsegsproject import LightweightNewsegsProject
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsvariable import variable
from newsegsmodelapp.registers import get_input_handler

local_project_provider = project_provider = CachedFromDatabaseNewsegsProjectProvider(db.get_engine)

def _create_text_field_values(
    proj: LightweightNewsegsProject,
    mm: LightweightNewsegsMetaModel,

    generic_text_ids: list[dict[str, Any]],
) -> list[Any]:
    text_values = []
    for text_id in generic_text_ids:
        match text_id.get('key'):
            case 'project-name':
                text_values.append(proj.name)
            case 'site-name':
                text_values.append(mm.model.location.name)
            case 'configuration-name':
                text_values.append(mm.name)
            case _:
                text_values.append(no_update)
    return text_values

def add_input_container_callbacks(app: NewsegsDash):
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
        container_id,
        
    ):
        if active_project_id is None:
            raise PreventUpdate
        trig = ctx.triggered_id
                        
        app_state = json.loads(app_state) if app_state else {}
        
        input_supersection = container_id.get('supersection')
        input_section = container_id.get('section')
        model_type = app_state.get('model_type', 'default')

        if not input_supersection or not input_section:
            raise PreventUpdate

        try:
            content_creator = get_input_container_content_creator(
                input_supersection, input_section, model_type
            )
        except KeyError as e:
            print('Content creator not found for ', str(container_id))
            print(e)
            return []

        return content_creator(active_project_id, app.project_provider)

    @app.callback(
        Output({'type': 'generic_text', 'section': ALL, 'key': ALL}, 'children'),

        Input('layout-update-trigger', 'data'),
        Input('active-project-id', 'data'),
        
        State({'type': 'generic_text', 'section': ALL, 'key': ALL}, 'id'),
        prevent_initial_call = True
    )
    def update_generic_text_contents(
        layout_update_trigger,
        active_project_id,
        generic_text_ids,
    ):
        if active_project_id is None:
            raise PreventUpdate

        provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)

        lproj = provider.get_lightweight_project(active_project_id)
        lmm = lproj.metamodels[[x.id for x in lproj.metamodels].index(lproj.focussed_metamodel_id)]

        text_values = _create_text_field_values(lproj, lmm, generic_text_ids)

        return text_values

    @app.callback(
        Output({
            'type': 'input-section-header', 
            'supersection': MATCH, 
            'section': MATCH
            },
            'children'
        ),

        Input({
            'type': 'input-group-config-update-trigger', 
            'supersection': MATCH, 'purpose': 'trigger',
            'section': MATCH, 'key': ALL, 'subindex': ALL,
            'parameter_index': ALL, 'vector_location': ALL
        }, 
        'data'),
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
        model_type = app_state.get('model_type', 'default')

        if not supersection or not section:
            raise PreventUpdate

        def _not_found(msg = None):
            print('Header creator not found for ', str(container_id))
            if msg:
                print(msg)
            return []
        
        try:
            content_creator = get_input_section_header_content_creator(
                supersection, section, model_type
            )
        except KeyError as e:
            return _not_found(e)

        if content_creator is None:
            return _not_found()
        
        return content_creator(active_project_id, app.project_provider)

    @app.callback(
        output = dict(
            input_values = Output(
                {
                    'type': 'single-input-config', 
                    'supersection': ALL, 'purpose': ALL,
                    'section': MATCH, 'key': MATCH, 'subindex': MATCH,
                    'parameter_index': ALL, 'vector_location': ALL,
                },
                'value',
            ),
            header_children = Output(
                {
                    'type': 'single-input-header', 
                    'supersection': ALL, 'purpose': 'header',
                    'section': MATCH, 'key': MATCH, 'subindex': MATCH,
                    'parameter_index': ALL, 'vector_location': ALL,
                },
                'children',
            ),
            trigger_data = Output(
                {
                    'type': 'input-group-config-update-trigger', 
                    'supersection': ALL, 'purpose': 'trigger',
                    'section': MATCH, 'key': MATCH, 'subindex': MATCH,
                    'parameter_index': ALL, 'vector_location': ALL,
                },
                'data',
            ),
        ),
        
        inputs = dict(
            changed_input_values = Input(
                {
                    'type': 'single-input-config', 
                    'supersection': ALL, 'purpose': ALL,
                    'section': MATCH, 'key': MATCH, 'subindex': MATCH,
                    'parameter_index': ALL, 'vector_location': ALL,
                }, 
                'value',
            ),
            changed_dropdown_values = Input(
                {
                    'type': 'input-dropdown',
                    'supersection': ALL, 'purpose': ALL,
                    'section': MATCH, 'key': MATCH, 'subindex': MATCH,
                    'parameter_index': ALL, 'vector_location': ALL,
                }, 
                'value',
            ),
            changed_toggle_values = Input(
                {
                    'type': 'input-toggle',
                    'supersection': ALL, 'purpose': ALL,
                    'section': MATCH, 'key': MATCH, 'subindex': MATCH,
                    'parameter_index': ALL, 'vector_location': ALL,
                }, 
                'value',
            ),
            changed_action_button_n_clicks = Input(
                {
                    'type': 'input-action-button',
                    'supersection': ALL, 'purpose': ALL,
                    'section': MATCH, 'key': MATCH, 'subindex': MATCH,
                    'parameter_index': ALL, 'vector_location': ALL,
                }, 
                'n_clicks',
            )
        ),

        state = dict(
            input_ids = State(
                {
                    'type': 'single-input-config', 
                    'supersection': ALL, 'purpose': ALL,
                    'section': MATCH, 'key': MATCH, 'subindex': MATCH,
                    'parameter_index': ALL, 'vector_location': ALL,
                }, 
                'id'
            ),
            header_ids = State(
                {
                    'type': 'single-input-header', 
                    'supersection': ALL, 'purpose': 'header',
                    'section': MATCH, 'key': MATCH, 'subindex': MATCH,
                    'parameter_index': ALL, 'vector_location': ALL,
                }, 
                'id'
            ),
            trigger_ids = State(
                {
                    'type': 'input-group-config-update-trigger', 
                    'supersection': ALL, 'purpose': 'trigger',
                    'section': MATCH, 'key': MATCH, 'subindex': MATCH,
                    'parameter_index': ALL, 'vector_location': ALL,
                }, 
                'id'
            ),
            active_project_id = State('active-project-id', 'data'),
            app_state = State('app-state', 'data'),
        ),

        prevent_initial_call = True
    )
    def react_to_input_change(
        input_ids,
        header_ids,
        trigger_ids,

        active_project_id,
        app_state,
        **kwargs
    ):
        
        print('Triggering object was ', ctx.triggered_id, type(ctx.triggered_id))
        print('Header ids are ', header_ids)
        print('Trigger ids are ', trigger_ids)
        print('Updated value is ', callback_utils.get_triggered_value())

        # Primary dispatch is on the purpose of the input
        trigger_id = ctx.triggered_id
        if trigger_id is None or active_project_id is None:
            raise PreventUpdate

        rval = callback_utils.create_noupdate_return()

        now = time.time_ns()
        
        match trigger_id['purpose']:
            case 'bound-lower' | 'bound-upper' | 'plot-intervals':
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
                                    rval['header_children'][idx] = content_creator(varid, mm)

                            # Update triggers
                            for idx, id in enumerate(trigger_ids):
                                match id['supersection']:
                                    case 'dsa':
                                        rval['trigger_data'][idx] = now

                            # Sync project to store
                            app.project_provider.upsert_component(proj)

                    case 'optim':
                        new_val = callback_utils.get_triggered_value()
                        proj = app.project_provider.get_project(active_project_id)
                        varid = make_varid(**trigger_id)
                        # For now, just going to hack this onto the dsa configuration
                        # Note that it will not be an observed component.
                        if not hasattr(proj.dsa_config, 'optim_config'):
                            proj.dsa_config.optim_config = {}
                        variable_bounds = proj.dsa_config.optim_config.setdefault('bounds', {})
                        bound = variable_bounds.setdefault(varid, {})
                        match trigger_id['purpose']:
                            case 'plot-intervals':
                                bound['intervals'] = new_val
                            case 'bound-lower':
                                bound['lower'] = new_val
                            case _:
                                bound['upper'] = new_val
                        proj.dsa_config.revision += 1
                        app.project_provider.upsert_component(proj)
                        
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
                        rval['input_values'][idx] = dsa_lower
                    if id['purpose'] == 'bound-upper':
                        rval['input_values'][idx] = dsa_upper

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
                        rval['header_children'][idx] = content_creator(varid, mm)
                
                # Update triggers with a dictionary, not an integer
                trig_val = json.dumps({
                    'message': 'dsa_bounds_modified',
                    'time': now
                })
                for idx, id in enumerate(trigger_ids):
                    match id['supersection']:
                        case 'dsa':
                            rval['trigger_data'][idx] = trig_val

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
                            rval['trigger_data'][idx] = trig_val

                # Sync project to store
                app.project_provider.upsert_component(proj)

            case _:
                try:
                    handler = get_input_handler(trigger_id['purpose'], trigger_id['type'], json.loads(app_state).get('model_type', 'default'))
                except KeyError:
                    print(f'No handlers for purpose {trigger_id["purpose"]}')
                    raise PreventUpdate
                if handler:
                    return handler(
                        trigger_id,
                        input_ids,
                        header_ids,
                        trigger_ids,
                        kwargs,
                        active_project_id,
                        app.project_provider,
                        return_dict = rval
                    )
                else:
                    print(f'No handlers for purpose {trigger_id["purpose"]}')
                    raise PreventUpdate

        return rval

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
        
        provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
        lproj = provider.get_lightweight_project(active_project_id)
        lmm = lproj.metamodels[lproj.focussed_metamodel_index]
        varprovider = cast(CachedFromDatabaseVariableProvider, project_provider.variable_provider)

        varid = make_varid(**container_ids[0])
        varuid =lmm.variables.get(varid)
        if varuid is None:
            raise PreventUpdate
        var = varprovider.get_full_lightweight_variable(varuid)
        bounds_input = create_dsa_bounds_inputs_scalar(var.dsa_bounds_type, var)
        
        if var.dsa_selected:
            cn = 'dsa-input-single-value-block'
        else:
            cn = 'dsa-input-single-value-block deselected'

        return (
            [bounds_input] * len(container_ids),
            [cn] * len(container_ids)
        )

    @app.callback(
        Output({
            'type': 'input-component', 
            'supersection': 'psa', 'purpose': 'input-group-container',
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL},
            'className'
        ),

        Input({
            'type': 'input-group-config-update-trigger', 
            'supersection': 'psa', 'purpose': 'trigger',
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL},
            'data'
        ),

        Input('active-project-id', 'data'),
        State('app-state', 'data'),
        State({
            'type': 'input-component', 
            'supersection': 'psa', 'purpose': 'input-group-container',
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL},
            'id'
        ),
    )
    def update_psa_input_contents(
        input_group_triggers,
        active_project_id,
        app_state,
        container_ids
    ):
        if not len(container_ids):
            raise PreventUpdate

        provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
        lproj = provider.get_lightweight_project(active_project_id)
        lmm = lproj.metamodels[lproj.focussed_metamodel_index]
        varprovider = cast(CachedFromDatabaseVariableProvider, project_provider.variable_provider)

        varid = make_varid(**container_ids[0])
        varuid =lmm.variables.get(varid)
        if varuid is None:
            raise PreventUpdate
        var = varprovider.get_full_lightweight_variable(varuid)
        
        if var.psa_selected:
            cn = 'psa-input-single-value-block'
        else:
            cn = 'psa-input-single-value-block deselected'

        return (
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
                'supersection': ALL, 'purpose': 'trigger',
                'section': ALL, 'key': ALL, 'subindex': ALL,
                'parameter_index': ALL, 'vector_location': ALL}, 
                'data'),

        State({'type': 'feedback-graph', 'section': ALL, 'key': ALL}, 'id'),
        State('active-project-id', 'data'),
        State('app-state', 'data'),

        prevent_initial_call = True,
        background = False,
    )
    def update_feedback_graphs(
        configuration_update_trigger,
        figure_ids,
        active_project_id,
        app_state
    ):
        app_state = json.loads(app_state) if app_state else {}
        model_type = app_state.get('model_type', 'default')

        figure_returns: list[Any] = [no_update] * len(figure_ids)

        for idx, id in enumerate(figure_ids):
            try:
                artist = get_feedback_graph_artist(id['key'], model_type)
            except KeyError:
                artist = None
            if artist:
                figure_returns[idx] = artist(active_project_id, local_project_provider)

        return figure_returns


    @app.callback(
        Output({
            'type': 'input-action-button', 
            'supersection': MATCH, 'purpose': 'variable-status-toggle',
            'section': MATCH, 'key': MATCH, 'subindex': ALL,
            'parameter_index': ALL, 'vector_location': ALL
        }, 'children'),
        Output({
            'type': 'input-action-button', 
            'supersection': MATCH, 'purpose': 'variable-status-toggle',
            'section': MATCH, 'key': MATCH, 'subindex': ALL,
            'parameter_index': ALL, 'vector_location': ALL
        }, 'color'),

        Input({
            'type': 'input-group-config-update-trigger', 
            'supersection': MATCH, 'purpose': 'trigger',
            'section': MATCH, 'key': MATCH, 'subindex': ALL,
            'parameter_index': ALL, 'vector_location': ALL
        }, 'data'),

        State({
            'type': 'input-action-button', 
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
        lproj = app.project_provider.get_lightweight_project(active_project_id)
        lmm = lproj.metamodels[lproj.focussed_metamodel_index]
        varid = make_varid(**triggered_id) # pyright: ignore[reportCallIssue]
        contents, colour = get_variable_sharing_status(lproj, lmm, varid)
        return [contents] * len(button_ids), [colour] * len(button_ids)
