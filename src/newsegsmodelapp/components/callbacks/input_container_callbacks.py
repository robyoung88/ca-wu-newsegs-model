"""
Callbacks to populate input containers when the project or active metamodel changes.
"""
import logging
logger = logging.getLogger(__name__)

import json
import time
from typing import Any, cast

from dash import ALL, MATCH, Input, Output, State, no_update
from dash import ctx
from dash.exceptions import PreventUpdate

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.backend.db.db_variable_provider import CachedFromDatabaseVariableProvider
from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.components.constants import CONFIGURATION_UPDATE_TRIGGER_ID
from newsegsmodelapp.components.input_components import get_variable_sharing_status
from newsegsmodelapp.components.variable_dash_component.vdc import create_dsa_bounds_inputs_scalar
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelapp.registers import get_feedback_graph_artist, get_input_container_content_creator, get_input_section_header_content_creator, get_single_input_header_content_creator
from newsegsmodelframework.newsegsmetamodel.lightweightnewsegsmetamodel import LightweightNewsegsMetaModel
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import make_varid
from newsegsmodelframework.newsegsproject.lightweightnewsegsproject import LightweightNewsegsProject
from newsegsmodelapp.registers import get_input_handler

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
        # Output(
        #     {'type': 'input-container', 'supersection': MATCH, 'section': MATCH},
        #     'children'
        # ),
        Output(
            {'type': 'input-section-header', 'supersection': MATCH, 'section': MATCH},
            'children'
        ),
        Output(
            {'type': 'input-container-hydration-interval', 'supersection': MATCH, 'section': MATCH},
            'n_intervals'
        ),

        Input('layout-update-trigger', 'data'),
        Input('active-project-id', 'data'),

        Input({
            'type': 'input-group-config-update-trigger', 
            'supersection': MATCH, 'purpose': 'trigger',
            'section': MATCH, 'key': ALL, 'subindex': ALL,
            'parameter_index': ALL, 'vector_location': ALL
        }, 
        'data'),

        State('app-state', 'data'),

        State({'type': 'input-container', 'supersection': MATCH, 'section': MATCH}, 'id'),
        
        prevent_initial_call = True
    )
    def update_input_header_contents(
        layout_update_trigger,
        active_project_id,
        input_group_update_trigger,
        app_state,
        container_id,
    ):
        if active_project_id is None:
            raise PreventUpdate
        t0 = time.perf_counter()
        trig = ctx.triggered_id

        update_header = True
        update_contents = isinstance(trig, str) # i.e. 'layout-update-trigger' or 'active-project-id'

        if not isinstance(trig, str):
            if callback_utils.get_triggered_value() is None:
                # Occurs after initial hydration
                raise PreventUpdate         

        app_state = json.loads(app_state) if app_state else {}
        
        supersection = container_id.get('supersection')
        section = container_id.get('section')
        model_type = app_state.get('model_type', 'default')

        if not supersection or not section:
            raise PreventUpdate

        rval = [no_update, no_update]

        def _not_found(creator_type):
            logger.exception('%s content creator not found for Container ID: %s', creator_type, container_id)

        if update_contents:
            rval[1] = 0

        if update_header:
            try:
                content_creator = get_input_section_header_content_creator(
                    supersection, section, model_type
                )
                if content_creator is None:
                    return _not_found('Input Section Header')
                else:
                    logger.debug(
                        'Creating Input Section Header contents using creator found for %s.%s.%s',
                        supersection, section, model_type
                    )
                    rval[0] = content_creator(active_project_id, app.project_provider)
            except KeyError as e:
                _not_found('Input Section Header')

        t1 = time.perf_counter()
        logger.info(f'Input Header for {supersection}, {section} created in {t1 - t0:.3f}s')
        return rval

    @app.callback(
        Output(
            {'type': 'input-container', 'supersection': MATCH, 'section': MATCH},
            'children'
        ),

        Input(
            {'type': 'input-container-hydration-interval', 'supersection': MATCH, 'section': MATCH},
            'n_intervals'
        ),

        State('active-project-id', 'data'),
        State('app-state', 'data'),
        State({'type': 'input-container', 'supersection': MATCH, 'section': MATCH}, 'id'),
        prevent_initial_call = True
    )
    def hydrate_input_container(n_intervals, active_project_id, app_state, container_id):
        if n_intervals != 1:
            raise PreventUpdate
        t0 = time.perf_counter()

        app_state = json.loads(app_state) if app_state else {}
                
        supersection = container_id.get('supersection')
        section = container_id.get('section')
        model_type = app_state.get('model_type', 'default')

        if not supersection or not section:
            raise PreventUpdate

        def _not_found(creator_type):
            logger.exception('%s content creator not found for Container ID: %s', creator_type, container_id)

        try:
            content_creator = get_input_container_content_creator(
                supersection, section, model_type
            )
            if content_creator is None:
                _not_found('Input Container')
            else:
                logger.debug(
                    'Creating Input Container contents using creator found for %s.%s.%s',
                    supersection, section, model_type
                )
                rval = content_creator(active_project_id, app.project_provider)
        except KeyError as e:
            _not_found('Input Container')

        t1 = time.perf_counter()
        logger.info(f'Input Container hydrated for {supersection}, {section} in {t1 - t0:.3f}s')
        return rval        

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
        t0 = time.perf_counter()

        provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)

        lproj = provider.get_lightweight_project(active_project_id)
        logger.debug('Getting lightweight project - Creating Generic Text Field contents')
        lmm = lproj.metamodels[[x.id for x in lproj.metamodels].index(lproj.focussed_metamodel_id)]

        logger.debug(
            'Creating Generic Text Field values based on Project ID: %s; with Focussed Metamodel ID: %s; (MM index: %d);',
            lproj.id, lmm.id, lproj.focussed_metamodel_index,
        )
        text_values = _create_text_field_values(lproj, lmm, generic_text_ids)
        t1 = time.perf_counter()
        logger.info(f'Generic Text Field values created in {t1 - t0:.3f}s')
        return text_values

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
        # Primary dispatch is on the purpose of the input
        trigger_id = ctx.triggered_id
        if trigger_id is None or active_project_id is None or len(ctx.triggered) > 1:
            raise PreventUpdate
        t0 = time.perf_counter()

        rval = callback_utils.create_noupdate_return()

        now = time.time_ns()

        logger.info(
            'Input change has triggered "react_to_input_change". Triggering object was %s and updated value is %s',
            ctx.triggered_id, callback_utils.get_triggered_value()
        )
        
        match trigger_id['purpose']:
            case 'bound-lower' | 'bound-upper' | 'plot-intervals':
                match trigger_id['supersection']:
                    case 'dsa':
                        logger.debug('Input change being handled as dsa bounds value change.')
                        new_val = callback_utils.get_triggered_value()

                        provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)
                        logger.debug('Getting lightweight project - Handling DSA bounds value change')
                        lproj = provider.get_lightweight_project(active_project_id)
                        lmm = lproj.metamodels[lproj.focussed_metamodel_index]
                        varid =  make_varid(**trigger_id)
                        varuid = lmm.variables.get(varid)
                        if not varuid:
                            raise PreventUpdate
                        var = provider.variable_provider.get_variable(varuid)

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
                                        id['supersection'], id['section'], lmm.model.model_type
                                    )
                                except KeyError:
                                    content_creator = None
                                if content_creator:
                                    varid =  make_varid(**trigger_id)
                                    rval['header_children'][idx] = content_creator(varid, lmm)

                            # Update triggers
                            for idx, id in enumerate(trigger_ids):
                                match id['supersection']:
                                    case 'dsa':
                                        rval['trigger_data'][idx] = now

                            provider.variable_provider.upsert_variable(var)

                            provider.increment_revision(lproj.id)
                            provider._component_provider.increment_revision(
                                lproj.table_config.id
                            )

                    case 'optim':
                        logger.debug('Input change being handled as optim bounds value or plot resolution change.')
                        new_val = callback_utils.get_triggered_value()

                        provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)
                        logger.debug('Getting lightweight project - Handling optim bounds value change')
                        lproj = provider.get_lightweight_project(active_project_id)

                        dsa_config = provider._component_provider.get_component(lproj.table_config.id)
                        if not hasattr(dsa_config, 'optim_config'):
                            dsa_config.optim_config = {}
                        variable_bounds = dsa_config.optim_config.setdefault('bounds', {})
                        
                        bound = variable_bounds.setdefault(varid, {})
                        match trigger_id['purpose']:
                            case 'plot-intervals':
                                bound['intervals'] = new_val
                            case 'bound-lower':
                                bound['lower'] = new_val
                            case _:
                                bound['upper'] = new_val

                        provider._component_provider.upsert_component(dsa_config, project_id = active_project_id)
                        provider.invalidate_cache_for_component(lproj.id)
                        
            case 'dsaboundtype':
                logger.debug('Input change being handled as dsa bounds type change.')
                new_val = callback_utils.get_triggered_value()

                provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)
                logger.debug('Getting lightweight project - Handling DSA bounds type change')
                lproj = provider.get_lightweight_project(active_project_id)
                lmm = lproj.metamodels[lproj.focussed_metamodel_index]
                varid =  make_varid(**trigger_id)
                varuid = lmm.variables.get(varid)
                if not varuid:
                    raise PreventUpdate
                var = provider.variable_provider.get_variable(varuid)
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
                            id['supersection'], id['section'], lmm.model.model_type
                        )
                    except KeyError:
                        content_creator = None
                    if content_creator:
                        varid =  make_varid(**trigger_id)
                        rval['header_children'][idx] = content_creator(varid, lmm)
                
                # Update triggers with a dictionary, not an integer
                trig_val = json.dumps({
                    'message': 'dsa_bounds_modified',
                    'time': now
                })
                for idx, id in enumerate(trigger_ids):
                    match id['supersection']:
                        case 'dsa':
                            rval['trigger_data'][idx] = trig_val

                # Sync variable and invalidate tables
                provider.variable_provider.upsert_variable(var)

                provider.increment_revision(lproj.id)
                provider._component_provider.increment_revision(
                    lproj.table_config.id
                )

            case 'dsa-active':
                logger.debug('Input change being handled as dsa active toggle change.')
                new_val = callback_utils.get_triggered_value()
                provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)
                logger.debug('Getting lightweight project - Handling DSA active status change')
                lproj = provider.get_lightweight_project(active_project_id)
                lmm = lproj.metamodels[lproj.focussed_metamodel_index]
                varid =  make_varid(**trigger_id)
                varuid = lmm.variables.get(varid)
                if not varuid:
                    raise PreventUpdate
                var = provider.variable_provider.get_variable(varuid)
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
                
                # Sync variable and invalidate tables
                provider.variable_provider.upsert_variable(var)

                provider.increment_revision(lproj.id)
                provider._component_provider.increment_revision(
                    lproj.table_config.id
                )

            case _:
                try:
                    handler = get_input_handler(trigger_id['purpose'], trigger_id['type'], json.loads(app_state).get('model_type', 'default'))
                except KeyError:
                    logger.exception('No input handlers found for purpose: %s', trigger_id['purpose'])
                    raise PreventUpdate
                if handler:
                    logger.debug(
                        'Input change being handled by input handler registered to purpose: %s; and type: %s; for model type: %s;',
                        trigger_id['purpose'], trigger_id['type'], json.loads(app_state).get('model_type', 'default')
                    )
                    rval = handler(
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
                    logger.exception('No input handlers found for purpose: %s', trigger_id['purpose'])
                    raise PreventUpdate

        t1 = time.perf_counter()
        logger.info(f'Input Change for {trigger_id['purpose']} {trigger_id['supersection']} handled in {t1 - t0:.3f}s')

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
        t0 = time.perf_counter()
        
        provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)
        logger.debug('Getting lightweight project - Handling DSA Input Group update')
        lproj = provider.get_lightweight_project(active_project_id)
        lmm = lproj.metamodels[lproj.focussed_metamodel_index]
        varprovider = cast(CachedFromDatabaseVariableProvider, app.project_provider.variable_provider)

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

        logger.debug(
            """
            Reacting to an Input Group Configuration Update Trigger for a DSA input container. 
            Affected container ids are: %s.
            """,
            container_ids
        )

        rval = (
            [bounds_input] * len(container_ids),
            [cn] * len(container_ids)
        )
        
        t1 = time.perf_counter()
        logger.info(f'DSA Input Change for {varid} handled in {t1 - t0:.3f}s')
        return rval

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
        t0 = time.perf_counter()

        provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)
        logger.debug('Getting lightweight project - Handling PSA Input Group update')
        lproj = provider.get_lightweight_project(active_project_id)
        lmm = lproj.metamodels[lproj.focussed_metamodel_index]
        varprovider = cast(CachedFromDatabaseVariableProvider, app.project_provider.variable_provider)

        varid = make_varid(**container_ids[0])
        varuid =lmm.variables.get(varid)
        if varuid is None:
            raise PreventUpdate
        var = varprovider.get_full_lightweight_variable(varuid)

        if var.psa_selected:
            cn = 'psa-input-single-value-block'
        else:
            cn = 'psa-input-single-value-block deselected'

        logger.debug(
            """
            Reacting to an Input Group Configuration Update Trigger for a PSA input container. 
            Affected container ids are: %s.
            """,
            container_ids
        )

        t1 = time.perf_counter()
        logger.info(f'PSA Input Change for {varid} handled in {t1 - t0:.3f}s')

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
        t0 = time.perf_counter()
        provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)
        logger.debug('Getting lightweight project - Updating site-location')
        lproj = provider.get_lightweight_project(active_project_id)
        lmm = lproj.metamodels[lproj.focussed_metamodel_index]
        
        loc_input = {
            'lat': lmm.location.lat,
            'lon': lmm.location.lon,
            'name': lmm.location.name
        }
        logger.debug('Setting site location in response to a trigger by "active-project-id".')
        t1 = time.perf_counter()
        logger.info(f'Site location synced in {t1 - t0:.3f}s')
        return json.dumps(loc_input)

    @app.callback(
        Output('feedback-graph-interval', 'n_intervals'),
        Input({
            'type': 'input-group-config-update-trigger', 
            'supersection': ALL, 'purpose': 'trigger',
            'section': ALL, 'key': ALL, 'subindex': ALL,
            'parameter_index': ALL, 'vector_location': ALL
        }, 'data'),
        prevent_initial_call = True
    )
    def trigger_feedback_graphs(configuration_update_trigger):
        return 0

    @app.callback(
        Output({'type': 'feedback-graph', 'section': ALL, 'key': ALL}, 'figure'),

        Input('feedback-graph-interval', 'n_intervals'),

        State({'type': 'feedback-graph', 'section': ALL, 'key': ALL}, 'id'),
        State('active-project-id', 'data'),
        State('app-state', 'data'),

        prevent_initial_call = True,
    )
    def update_feedback_graphs(
        feedback_graph_interval,
        figure_ids,
        active_project_id,
        app_state
    ):
        if feedback_graph_interval != 1:
            raise PreventUpdate
        t0 = time.perf_counter()
        app_state = json.loads(app_state) if app_state else {}
        model_type = app_state.get('model_type', 'default')

        figure_returns: list[Any] = [no_update] * len(figure_ids)

        for idx, id in enumerate(figure_ids):
            try:
                artist = get_feedback_graph_artist(id['key'], model_type)
            except KeyError:
                artist = None
            if artist:
                logger.debug(
                    'Creating feedback graph for key: %s. Trigger was: %s', id['key'], ctx.triggered_id)
                figure_returns[idx] = artist(active_project_id, app.project_provider)

        t1 = time.perf_counter()
        logger.info(f'Feedback Graphs updated in {t1 - t0:.3f}s')

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
        t0 = time.perf_counter()

        triggered_id = ctx.triggered_id
        logger.debug('Getting lightweight project - Updating variable status badge')
        lproj = app.project_provider.get_lightweight_project(active_project_id)
        lmm = lproj.metamodels[lproj.focussed_metamodel_index]
        varid = make_varid(**triggered_id) # pyright: ignore[reportCallIssue]
        contents, colour = get_variable_sharing_status(lproj, lmm, varid)

        logger.debug('Updated the variable status badge for variable %s, triggered by %s', varid, triggered_id)
        t1 = time.perf_counter()
        logger.info(f'Variable Status badge for {varid} updated in {t1 - t0:.3f}s')
        return [contents] * len(button_ids), [colour] * len(button_ids)
