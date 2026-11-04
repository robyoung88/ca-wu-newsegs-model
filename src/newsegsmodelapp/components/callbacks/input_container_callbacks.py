"""
Callbacks to populate input containers when the project or active metamodel changes.
"""
import copy
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
from newsegsmodelapp.backend.db import db_staleness
from newsegsmodelapp.components import callback_utils, staleness
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
        output = dict(
            headers = Output(
                {'type': 'input-section-header', 'supersection': ALL, 'section': ALL},
                'children'    
            ),
            input_container_triggers = Output(
                {'type': 'input-container-hydration-interval', 'supersection': ALL, 'section': ALL},
                'n_intervals'
            ),
        ),
        inputs = dict(
            layout_update_trigger = Input('layout-update-trigger', 'data'),
            active_project_id = Input('active-project-id', 'data'),
            input_group_update_trigger = Input({
                'type': 'input-group-config-update-trigger', 
                'supersection': ALL, 'purpose': 'trigger',
                'section': ALL, 'key': ALL, 'subindex': ALL,
                'parameter_index': ALL, 'vector_location': ALL
            }, 'data'),
        ),
        state  = dict(
            app_state = State('app-state', 'data')
        ),
        prevent_initial_call = True
    )
    def update_input_header_contents(
        active_project_id,
        app_state,
        **kwargs
    ):
        if active_project_id is None:
            raise PreventUpdate
        t0 = time.perf_counter()
        trig = ctx.triggered_id

        if not isinstance(trig, str):
            if callback_utils.get_triggered_value() is None:
                # input-group-config-update-trigger are fired after initial hydration with None
                raise PreventUpdate
        
        rval = callback_utils.create_noupdate_return()

        update_all_headers = isinstance(trig, str) # i.e. 'layout-update-trigger' or 'active-project-id'
        # If trigger is not a layout change (or project change) then no need to redraw the inputs
        update_contents = update_all_headers                 

        app_state = json.loads(app_state) if app_state else {}
        model_type = app_state.get('model_type', 'default')

        id_roots = []
        if update_all_headers:
            for container_id in ctx.outputs_grouping['headers']:
                id_roots.append(container_id['id'])
        else:
            container_id = {
                'type': 'input-section-header',
                'supersection': trig['supersection'],
                'section': trig['section'],
            }
            # Not every section has a header (e.g. those of optimisation), so only update one on the page
            if not any(x['id'] == container_id for x in ctx.outputs_grouping['headers']):
                raise PreventUpdate
            id_roots = [container_id]

        for container_id in id_roots:
            supersection = container_id.get('supersection')
            section = container_id.get('section')
            
            def _not_found(creator_type):
                logger.exception('%s content creator not found for Container ID: %s', creator_type, container_id)

            if update_contents:
                # set the intervals count to 0
                trigger_id = copy.copy(container_id)
                trigger_id['type'] = 'input-container-hydration-interval'
                callback_utils.update_property_by_id(
                    trigger_id,
                    'n_intervals',
                    0,
                    rval
                )

            try:
                content_creator = get_input_section_header_content_creator(
                    supersection, section, model_type
                )
                if content_creator is None:
                    return _not_found('Input Section Header')
                else:
                    logger.info(
                        'Creating Input Section Header contents using creator found for %s.%s.%s',
                        supersection, section, model_type
                    )
                    callback_utils.update_property_by_id(
                        container_id,
                        'children',
                        content_creator(active_project_id, app.project_provider),
                        rval
                    )
            except KeyError as e:
                _not_found('Input Section Header')

        t1 = time.perf_counter()
        logger.info(f'Input Header(s) created in {t1 - t0:.3f}s')
        return rval

    @app.callback(
        output = dict(
            containers = Output(
                {'type': 'input-container', 'supersection': ALL, 'section': ALL},
                'children'
            )
        ),
        inputs = dict(
            hydration_trigger = Input(
                {'type': 'input-container-hydration-interval', 'supersection': ALL, 'section': ALL},
                'n_intervals'
            ),
        ),
        state = dict(
            active_project_id = State('active-project-id', 'data'),
            app_state = State('app-state', 'data'),
        ),
        prevent_initial_call = True
    )
    def hydrate_input_container(
        active_project_id, 
        app_state, 
        **kwargs
    ):
        t0 = time.perf_counter()

        rval = callback_utils.create_noupdate_return()
        
        app_state = json.loads(app_state) if app_state else {}
        model_type = app_state.get('model_type', 'default')

        # Intervals are reset to 0 by update_input_header_contents and then tick to 1;
        # only hydrate on the tick, or each container is built twice
        triggers = [x for x in ctx.triggered if x['value'] == 1]
        if not triggers:
            raise PreventUpdate

        for trig in triggers:
            trig = json.loads(trig['prop_id'].rsplit('.',1)[0])
            supersection = trig.get('supersection')
            section = trig.get('section')

            container_id = dict(
                type = 'input-container',
                supersection = supersection,
                section = section
            )

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
                    callback_utils.update_property_by_id(
                        container_id,
                        'children',
                        content_creator(active_project_id, app.project_provider),
                        rval
                    )
            except KeyError as e:
                _not_found('Input Container')

        t1 = time.perf_counter()
        logger.info(f'Input Container(s) hydrated in {t1 - t0:.3f}s')
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
            editor_children = Output(
                {
                    'type': 'input-group-editor',
                    'supersection': ALL, 'purpose': 'editor',
                    'section': MATCH, 'key': MATCH, 'subindex': MATCH,
                    'parameter_index': ALL, 'vector_location': ALL,
                },
                'children',
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
            ),
            # Opening a row: html.Details does not report `open`, so the clicks on its summary are counted
            changed_summary_n_clicks = Input(
                {
                    'type': 'input-summary',
                    'supersection': ALL, 'purpose': 'group-editor-toggle',
                    'section': MATCH, 'key': MATCH, 'subindex': MATCH,
                    'parameter_index': ALL, 'vector_location': ALL,
                },
                'n_clicks',
            ),
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
            # Not a named argument, so passed to the input handlers in their calling_dict
            editor_ids = State(
                {
                    'type': 'input-group-editor',
                    'supersection': ALL, 'purpose': 'editor',
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
                            db_staleness.mark_inputs_changed(
                                staleness.metamodels_using_variable(lproj, varuid), 'dsa'
                            )

                    case 'optim':
                        logger.debug('Input change being handled as optim bounds value or plot resolution change.')
                        new_val = callback_utils.get_triggered_value()

                        provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)
                        logger.debug('Getting lightweight project - Handling optim bounds value change')
                        lproj = provider.get_lightweight_project(active_project_id)
                        lmm = lproj.metamodels[lproj.focussed_metamodel_index]
                        varid = make_varid(**trigger_id)
                        varuid = lmm.variables.get(varid)
                        if not varuid:
                            raise PreventUpdate
                        var = provider.variable_provider.get_variable(varuid)

                        match trigger_id['purpose']:
                            case 'plot-intervals':
                                # An emptied input leaves the resolution as it was
                                if new_val is None or int(new_val) == var.optim_plot_intervals:
                                    raise PreventUpdate
                                var.optim_plot_intervals = int(new_val)
                            case 'bound-lower':
                                # An emptied input unsets the bound, which falls back to the input limit
                                if new_val == var.optim_min:
                                    raise PreventUpdate
                                var.optim_min = new_val
                            case _:
                                if new_val == var.optim_max:
                                    raise PreventUpdate
                                var.optim_max = new_val

                        provider.variable_provider.upsert_variable(var)
                        provider.invalidate_cache_for_component(lproj.id)

                        # Plot intervals only set the resolution of the marginal plot
                        if trigger_id['purpose'] != 'plot-intervals':
                            # Configurations sharing the variable share its bounds
                            db_staleness.mark_inputs_changed(
                                staleness.metamodels_using_variable(lproj, varuid), 'optim'
                            )
                            for idx, id in enumerate(trigger_ids):
                                if id['supersection'] == 'optim':
                                    rval['trigger_data'][idx] = now
                        
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
                db_staleness.mark_inputs_changed(
                    staleness.metamodels_using_variable(lproj, varuid), 'dsa'
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

                # Sync the selection onto the independent instances of the variable in the other metamodels,
                # so that a whole-project DSA varies the same variables in every metamodel
                changed_mm_ids = list(staleness.metamodels_using_variable(lproj, varuid))
                for other_lmm in lproj.metamodels:
                    other_varuid = other_lmm.variables.get(varid)
                    if not other_varuid or other_varuid == varuid:
                        continue
                    other_var = provider.variable_provider.get_variable(other_varuid)
                    if (
                        not other_var
                        or not (other_var.dsa_possible and other_var.dsa_selectable)
                        or other_var.dsa_selected == new_val
                    ):
                        continue
                    other_var.dsa_selected = new_val
                    provider.variable_provider.upsert_variable(other_var)
                    for mm_id in staleness.metamodels_using_variable(lproj, other_varuid):
                        if mm_id not in changed_mm_ids:
                            changed_mm_ids.append(mm_id)

                provider.increment_revision(lproj.id)
                provider._component_provider.increment_revision(
                    lproj.table_config.id
                )
                db_staleness.mark_inputs_changed(changed_mm_ids, 'dsa')

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
                        {**kwargs, 'app_state': app_state},
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

        # Not an Input: a project or configuration change rehydrates the whole input container,
        # which builds this content afresh
        State('active-project-id', 'data'),
        State('app-state', 'data'),
        State({
            'type': 'input-component', 
            'supersection': 'dsa', 'purpose': 'bounds-container',
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL},
            'id'
        ),
        # The trigger is inserted with the input group on hydration, which has already built this content
        prevent_initial_call = True,
    )
    def update_dsa_input_contents(
        input_group_triggers,
        active_project_id,
        app_state,
        container_ids
    ):
        if not len(container_ids) or active_project_id is None:
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

        # Not an Input: a project or configuration change rehydrates the whole input container,
        # which builds this content afresh
        State('active-project-id', 'data'),
        State('app-state', 'data'),
        State({
            'type': 'input-component', 
            'supersection': 'psa', 'purpose': 'input-group-container',
            'section': MATCH, 'key': MATCH, 'subindex': MATCH,
            'parameter_index': ALL, 'vector_location': ALL},
            'id'
        ),
        # The trigger is inserted with the input group on hydration, which has already built this content
        prevent_initial_call = True,
    )
    def update_psa_input_contents(
        input_group_triggers,
        active_project_id,
        app_state,
        container_ids
    ):
        if not len(container_ids) or active_project_id is None:
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
            'name': lmm.location.name,
            # Lets the map apply this location only to the configuration it came from
            'metamodel_id': lmm.id,
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
