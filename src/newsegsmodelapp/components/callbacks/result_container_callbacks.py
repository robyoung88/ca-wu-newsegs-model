"""Result container callbacks module.

TODO: Describe the purpose of the module.
"""
import logging
logger = logging.getLogger(__name__)

import json
import time
from typing import Any, cast

from dash import ALL, MATCH, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate
# Cached results are unpickled inside callbacks, and Dash refuses component
# libraries first imported there. Tables cached before the move to AG Grid hold
# dash_extensions.Purify components, so register the library at startup.
import dash_extensions # noqa: F401

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.components import callback_utils, staleness
from newsegsmodelapp import registers
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelapp.registers import get_result_container_content_creator, get_result_section_header_content_creator


def add_result_container_callbacks(app: NewsegsDash):
    """
    Callbacks to populate output containers.
    
    An ouput container is identified by:
    {'type': 'result-container', 'supersection': 'XXX', 'section': 'XXX'}
    """

    @app.callback(
        output = dict(
            containers = Output(
               {
                    'type': 'result-container', 'purpose': 'container',
                    'supersection': ALL, 'section': ALL,
                    'key': ALL, 'subindex': ALL
                }, 'children' 
            ),
            rendered_project_ids = Output(
                {
                    'type': 'result-container', 'purpose': 'container',
                    'supersection': ALL, 'section': ALL,
                    'key': ALL, 'subindex': ALL
                }, 'data-rendered-project-id'
            ),
        ),
        inputs = dict(
            page = Input('url', 'pathname'),
            layout_update_trigger = Input('layout-update-trigger', 'data'),
            active_project_id = Input('active-project-id', 'data'),
        ),
        state = dict(
            app_state = State('app-state', 'data'),
            container_ids = State({
                'type': 'result-container', 'purpose': 'container',
                'supersection': ALL, 'section': ALL,
                'key': ALL, 'subindex': ALL
            }, 'id'),
            rendered_project_ids = State({
                'type': 'result-container', 'purpose': 'container',
                'supersection': ALL, 'section': ALL,
                'key': ALL, 'subindex': ALL
            }, 'data-rendered-project-id'),
        ),
        prevent_initial_call = True
    )
    def update_output_container_contents(
        active_project_id,
        app_state,
        container_ids,
        rendered_project_ids,
        **kwargs
    ):
        if active_project_id is None:
            raise PreventUpdate
        t0 = time.perf_counter()

        # Do not update layout if only redrawing the existing project
        triggered_id = ctx.triggered_id
        is_project_trigger = (triggered_id == 'active-project-id')

        app_state = json.loads(app_state) if app_state else {}
        model_type = app_state.get('model_type', 'default')

        rval = callback_utils.create_noupdate_return()
        for container_id, rendered_project_id in zip(container_ids, rendered_project_ids):
            project_has_changed = (active_project_id != rendered_project_id)
            if is_project_trigger and not project_has_changed:
                continue

            section = container_id.get('section')
            key_ = container_id.get('key')

            def _not_found():
                logger.exception(
                    'Result container content creator not found for Container ID: %s',
                    container_id
                )
    
            try:
                content_creator = get_result_container_content_creator(
                    key_, section, model_type
                )
                if content_creator is None:
                    _not_found()
                else:
                    logger.info(
                        'Creating Result Container contents using creator found for %s.%s.%s',
                        key_, section, model_type
                    )
                    callback_utils.update_property_by_id(
                        container_id,
                        'children',
                        content_creator(active_project_id, app.project_provider),
                        rval
                    )
                    callback_utils.update_property_by_id(
                        container_id,
                        'data-rendered-project-id',
                        active_project_id,
                        rval
                    )

            except KeyError as e:
                _not_found()

        t1 = time.perf_counter()
        logger.info(f'Result Container(s) created in {t1 - t0:.3f}s')
        return rval

    @app.callback(
        output = dict(
            containers = Output(
               {
                    'type': 'result-section-header', 'purpose': 'header',
                    'supersection': ALL, 'section': ALL,
                    'key': ALL, 'subindex': ALL
                }, 'children' 
            )
        ),
        inputs = dict(
            postaction_triggers = Input({
                'type': 'postaction-trigger', 'purpose': 'trigger',
                'supersection': ALL, 'section': ALL,
                'key': ALL, 'subindex': ALL
            }, 'data'),
            ann_hori_toggle = Input(
                {'type': 'annual-horizon-toggle', 'page': ALL}, 
                'value'
            ),
            active_project_id = Input('active-project-id', 'data'),
            trigger_check_stale = Input('trigger-check-stale', 'data'),
        ),
        state = dict(
            app_state = State('app-state', 'data')
        ),
        prevent_initial_call = False, # Want to trigger as we change page
    )
    def update_result_section_header_contents(
        ann_hori_toggle,
        active_project_id,
        app_state,
        **kwargs
    ):
        if active_project_id is None:
            raise PreventUpdate
        t0 = time.perf_counter()

        rval = callback_utils.create_noupdate_return()
        if len(rval) == 0:
            raise PreventUpdate

        trig_id = ctx.triggered_id
        update_all_headers = isinstance(trig_id, str) or trig_id is None or trig_id['type'] == 'annual-horizon-toggle'

        if update_all_headers:
            headers_for_update = [x['id'] for x in ctx.outputs_grouping['containers']]
        else:
            headers_for_update = []
            for trig in ctx.triggered:
                trig = json.loads(trig['prop_id'].rsplit('.',1)[0])
                trig['purpose'] = 'header'
                trig['type'] = 'result-section-header'
                del trig['subindex']
                del trig['supersection']
                headers_for_update.extend(
                    [
                        x['id'] for x in ctx.outputs_grouping['containers']
                        if callback_utils.intersection_values_match(trig, x['id'])
                    ]
                )

        if not headers_for_update:
            return rval

        app_state = json.loads(app_state) if app_state else {}
        model_type = app_state.get('model_type', 'default')

        contents_by_section = {}
        ann_hori_toggle = ann_hori_toggle[0] if len(ann_hori_toggle) else False

        for container_id in headers_for_update:
            section = container_id['section']
            if section in contents_by_section:
                callback_utils.update_property_by_id(
                    container_id,
                    'children',
                    contents_by_section[section],
                    rval
                )
                continue
            key = container_id['key']
            content_creator = get_result_section_header_content_creator(
                key, section, model_type
            )
            if content_creator is None:
                continue
            logger.info(
                'Creating Result Section Header contents using creator found for %s.%s.%s',
                key, section, model_type
            )
            contents = content_creator(
                active_project_id, app.project_provider, app.results_provider, ann_hori_toggle
            )
            contents_by_section[section] = contents
            callback_utils.update_property_by_id(
                container_id,
                'children',
                contents,
                rval
            )

        t1 = time.perf_counter()
        logger.info(f'Result Section Header(s) created in {t1 - t0:.3f}s')

        return rval

    @app.callback(
        output = dict(
            table = Output({
                'type': 'result-table', 'purpose': 'container',
                'supersection': ALL, 'section': ALL,
                'key': ALL, 'subindex': ALL
            }, 'children'),
            data_is_stale = Output({
                'type': 'result-table', 'purpose': 'container',
                'supersection': ALL, 'section': ALL,
                'key': ALL, 'subindex': ALL
            }, 'data-is-stale'),
            data_rendered_project_id = Output({
                'type': 'result-table', 'purpose': 'container',
                'supersection': ALL, 'section': ALL,
                'key': ALL, 'subindex': ALL
            }, 'data-rendered-project-id'),
            data_rendered_project_table_revision = Output({
                'type': 'result-table', 'purpose': 'container',
                'supersection': ALL, 'section': ALL,
                'key': ALL, 'subindex': ALL
            }, 'data-rendered-project-table-revision'),
            data_rendered_ann_hori_state = Output({
                'type': 'result-table', 'purpose': 'container',
                'supersection': ALL, 'section': ALL,
                'key': ALL, 'subindex': ALL
            }, 'data-rendered-ann-hori-state'),
        ),
        inputs = dict(
            postaction_triggers = Input({
                'type': 'postaction-trigger', 'purpose': 'trigger',
                'supersection': ALL, 'section': ALL,
                'key': ALL, 'subindex': ALL
            }, 'data'),
            table_options = dict(
                values = Input({
                    'type': 'result-table-option', 'purpose': ALL,
                    'supersection': ALL, 'section': ALL,
                    'key': ALL, 'subindex': ALL
                }, 'value'),
                ids = State({
                    'type': 'result-table-option', 'purpose': ALL,
                    'supersection': ALL, 'section': ALL,
                    'key': ALL, 'subindex': ALL
                }, 'id'),
            ),
            ann_hori_toggle = Input(
                {'type': 'annual-horizon-toggle', 'page': ALL}, 
                'value'
            ),
            active_project_id_interval = Input('delayed-result-container-refill-interval', 'n_intervals'),
        ),
        state = dict(
            active_project_id = State('active-project-id', 'data'),
            app_state = State('app-state', 'data'),
            container_ids = State({
                'type': 'result-table', 'purpose': 'container',
                'supersection': ALL, 'section': ALL,
                'key': ALL, 'subindex': ALL
            }, 'id'),
            rendered_project_ids = State({
                'type': 'result-table', 'purpose': 'container',
                'supersection': ALL, 'section': ALL,
                'key': ALL, 'subindex': ALL
            }, 'data-rendered-project-id'),
            rendered_project_table_revisions =  State({
                'type': 'result-table', 'purpose': 'container',
                'supersection': ALL, 'section': ALL,
                'key': ALL, 'subindex': ALL
            }, 'data-rendered-project-table-revision'),
            rendered_ann_hori_states =  State({
                'type': 'result-table', 'purpose': 'container',
                'supersection': ALL, 'section': ALL,
                'key': ALL, 'subindex': ALL
            }, 'data-rendered-ann-hori-state'),
        ),
        prevent_initial_call = False, 
    )
    def update_result_section_contents(
        table_options,
        ann_hori_toggle,
        active_project_id,
        app_state,
        container_ids,
        rendered_project_ids,
        rendered_project_table_revisions,
        rendered_ann_hori_states,
        **kwargs
    ):
        if active_project_id is None or container_ids is None or not len(container_ids):
            raise PreventUpdate

        trig_id = ctx.triggered_id
        # The interval is reset to 0 on project change and then ticks to 1; only act on the tick
        if isinstance(trig_id, str) and trig_id == 'delayed-result-container-refill-interval':
            if callback_utils.get_triggered_value() != 1:
                raise PreventUpdate

        t0 = time.perf_counter()
        rval = callback_utils.create_noupdate_return()

        update_all_tables = isinstance(trig_id, str) or trig_id == None
        if update_all_tables:
            tables_for_update = [x['id'] for x in ctx.outputs_grouping['table']]
        else:
            tables_for_update = []
            for trig in ctx.triggered:
                trig = json.loads(trig['prop_id'].rsplit('.',1)[0])
                trig['purpose'] = 'container'
                trig['type'] = 'result-table'
                del trig['subindex']
                del trig['supersection']
                tables_for_update.extend(
                    [
                        x['id'] for x in ctx.outputs_grouping['table'] 
                        if callback_utils.intersection_values_match(trig, x['id'])
                    ]
                )
        if not tables_for_update:
            return rval

        app_state = json.loads(app_state) if app_state else {}
        model_type = app_state.get('model_type', 'default')
        
        contents_by_section_subindex = {}
        """
        Local store for contents to prevent redrawing within single call, keyed
        by (section, key, subindex): containers share a section ('tabledraw'),
        so the key is needed to tell their tables apart
        """
        
        # Do not update if the toggle status has not changed, the project is the same,
        # and the table revision number is the same.
        logger.debug('Getting lightweight project - Updating Result Table Containers')
        lproj = app.project_provider.get_lightweight_project(active_project_id)
        table_rev = lproj.table_config.revision
        # The toggle's value is None until first used; normalise so that the
        # rendered state recorded below can match on the next call
        ann_hori_toggle = bool(ann_hori_toggle[0]) if len(ann_hori_toggle) else False

        rendered_project = {
            (k['section'], k['key']) : v for k, v in zip(container_ids, rendered_project_ids)
        }
        rendered_revision = {
            (k['section'], k['key']) : v for k, v in zip(container_ids, rendered_project_table_revisions)
        }
        rendered_ann_hori_state = {
            (k['section'], k['key']) : v for k, v in zip(container_ids, rendered_ann_hori_states)
        }

        options_per_table = {}
        for id, val in zip(table_options['ids'], table_options['values']):
            lookup = (id['section'], id['key'])
            options_per_table.setdefault(lookup, {})[id['purpose']] = val

        for container_id in tables_for_update:
            section = container_id['section']
            key = container_id['key']
            lookup = (section, key)
            if rendered_ann_hori_state.get(lookup) is not None and rendered_ann_hori_state[lookup] == ann_hori_toggle:
                if rendered_project.get(lookup) is not None and rendered_project[lookup] == active_project_id:
                    if rendered_revision.get(lookup) is not None and rendered_revision[lookup] == table_rev:
                        continue

            subindex = int(container_id.get('subindex'))
            ss = (section, key, subindex)
            if ss in contents_by_section_subindex:
                callback_utils.update_property_by_id(
                    container_id,
                    'children',
                    contents_by_section_subindex[ss][0],
                    rval
                )
                callback_utils.update_property_by_id(
                    container_id, 'data-is-stale',
                    contents_by_section_subindex[ss][1],
                    rval
                )
                callback_utils.update_property_by_id(
                    container_id, 'data-rendered-project-id',
                    active_project_id, rval
                )
                callback_utils.update_property_by_id(
                    container_id, 'data-rendered-project-table-revision',
                    table_rev, rval
                )
                callback_utils.update_property_by_id(
                    container_id, 'data-rendered-ann-hori-state',
                    ann_hori_toggle, rval
                )
                continue
            
            opts = options_per_table.get(lookup, {})

            # 1) Find any custom table providers for this table / model
            table_name = key
            table_getter = None
            try:
                table_getter = registers.get_table_getter(table_name, model_type)
            except KeyError:
                pass

            if table_getter is not None:
                logger.debug(
                    'Updating Result Table Container using custom getter: Section: %s; Subindex: %s; Key: %s;',
                    section, subindex, key
                )
                opts['ann_hori_toggle'] = ann_hori_toggle
                opts['subindex'] = subindex
                res, rev = table_getter(
                    active_project_id, opts, app.project_provider, app.results_provider
                )

            else:
                # 2) Fall back to conventional table lookup
                if subindex > 0:
                    # Optionally vary the table name from default if subindex != 0
                    subindex_map = registers.get_table_subindex_map(key, model_type)
                    if subindex_map:
                        table_name = subindex_map[subindex]

                # Try with annual or to horizon subtable suffix
                sub_table_name = table_name + '_hori' if ann_hori_toggle else table_name + '_ann'
                res, rev = app.results_provider.get_result(sub_table_name, lproj.table_config)
                
                if res is None:
                    # Retry without the subtable suffix
                    res, rev = app.results_provider.get_result(table_name, lproj.table_config)
                    logger.debug(
                        'Updating Result Table Container using standard getter: Section: %s; Subindex: %s; Key: %s;',
                        section, subindex, table_name
                    )
                else:
                    logger.debug(
                        'Updating Result Table Container using standard getter: Section: %s; Subindex: %s; Key: %s;',
                        section, subindex, sub_table_name
                    )
            
            if res is not None:
                logger.debug(
                    'Table found is for revision %d; Current project table revision is %d. Result Table Container Section: %s; Subindex: %s; Key: %s;',
                    rev, lproj.table_config.revision, section, subindex, key
                )
                stale = rev != lproj.table_config.revision
                contents_by_section_subindex[ss] = res, stale
                callback_utils.update_property_by_id(
                    container_id,
                    'children',
                    contents_by_section_subindex[ss][0],
                    rval
                )
                callback_utils.update_property_by_id(
                    container_id, 'data-is-stale',
                    contents_by_section_subindex[ss][1],
                    rval
                )
                callback_utils.update_property_by_id(
                    container_id, 'data-rendered-project-id',
                    active_project_id, rval
                )
                callback_utils.update_property_by_id(
                    container_id, 'data-rendered-project-table-revision',
                    table_rev, rval
                )
                callback_utils.update_property_by_id(
                    container_id, 'data-rendered-ann-hori-state',
                    ann_hori_toggle, rval
                )

            else:
                callback_utils.update_property_by_id(
                    container_id,
                    'children',
                    [],
                    rval
                )
                callback_utils.update_property_by_id(
                    container_id, 'data-rendered-project-id',
                    active_project_id, rval
                )
                callback_utils.update_property_by_id(
                    container_id, 'data-is-stale',
                    True,
                    rval
                )
                callback_utils.update_property_by_id(
                    container_id, 'data-rendered-project-table-revision',
                    -1, rval
                )

        t1 = time.perf_counter()
        logger.info(f'Result Table (s) created in {t1 - t0:.3f}s')

        return rval

    # Graphs can't hold data attributes, so can't use them directly
    # for state monitoring.
    @app.callback(
        Output({
            'type': 'result-figure', 'purpose': 'container',
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'figure'),

        Input({
            'type': 'postaction-trigger', 'purpose': 'trigger',
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'data'),

        Input({
            'type': 'result-table-option', 'purpose': ALL,
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'value'),

        Input({'type': 'annual-horizon-toggle', 'page': ALL}, 'value'),
        Input('active-project-id', 'data'),
        State('app-state', 'data'),

        State({
            'type': 'result-figure', 'purpose': 'container',
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'id'),
        State({
            'type': 'result-table-option', 'purpose': ALL,
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'id'),
        prevent_initial_call = True
    )
    def update_result_figure_contents(
        postaction_triggers,
        result_table_options,
        ann_hori_toggle,
        active_project_id,
        app_state,
        container_ids,
        option_ids,
    ):
        if active_project_id is None or container_ids is None or not len(container_ids):
            raise PreventUpdate
        t0 = time.perf_counter()

        provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)
        logger.debug('Getting lightweight project - Updating Result Figure Containers')
        lproj = provider.get_lightweight_project(active_project_id)
        table_rev = lproj.table_config.revision
        ann_hori_toggle = ann_hori_toggle[0] if len(ann_hori_toggle) else False

        return_contents: list[Any] = [no_update] * len(container_ids)

        contents_by_section_subindex = {}

        app_state = json.loads(app_state) if app_state else {}
        model_type = app_state.get('model_type', 'default')

        table_options = {}
        for optid, optval in zip(option_ids, result_table_options):
            table_options[optid['purpose']] = optval

        for idx, cid in enumerate(container_ids):
            res = None
            rev = None
            section = cid.get('section')
            subindex = int(cid.get('subindex'))
            ss = (section, subindex)
            if ss in contents_by_section_subindex:
                return_contents[idx] = contents_by_section_subindex[ss]
                continue

            key = cid.get('key')
            if not section or not key:
                continue

            table_name = key
            table_getter = None
            try:
                figure_getter = registers.get_table_getter(table_name, model_type)
            except KeyError:
                continue
            if figure_getter is not None:
                logger.debug(
                    'Updating Result Figure Container using custom getter: Section: %s; Subindex: %s; Key: %s;',
                    section, subindex, key
                )
                table_options['ann_hori_toggle'] = ann_hori_toggle
                table_options['subindex'] = subindex
                res, rev = figure_getter(
                    active_project_id, table_options, app.project_provider, app.results_provider
                )
            
            if res is not None:
                logger.debug(
                    'Figure found is for revision %d; Current project table revision is %d. Result Figure Container Section: %s; Subindex: %s; Key: %s;',
                    rev, lproj.table_config.revision, section, subindex, key
                )
                contents_by_section_subindex[ss] = res
                return_contents[idx] = res
        t1 = time.perf_counter()
        logger.info(f'Result Figure for {section}, {subindex}, {key} created in {t1 - t0:.3f}s')

        return return_contents 
        
    @app.callback(
        output = dict(
            indicator_class = Output(
                {'type': staleness.INDICATOR_TYPE, 'page': ALL, 'process': ALL},
                'className',
            ),
            tooltip_children = Output(
                {'type': staleness.TOOLTIP_TYPE, 'page': ALL, 'process': ALL},
                'children',
            ),
            header_class = Output(
                {'type': 'result-header-single-config', 'table': ALL, 'metamodel': ALL},
                'className',
            ),
        ),
        inputs = dict(
            config_update = Input(
                {
                    'type': 'input-group-config-update-trigger', 
                    'supersection': ALL, 'purpose': 'trigger',
                    'section': ALL, 'key': ALL, 'subindex': ALL,
                    'parameter_index': ALL, 'vector_location': ALL,
                }, 
                'data'
            ),
            postaction_triggers = Input(
                {
                    'type': 'postaction-trigger', 'purpose': 'trigger',
                    'supersection': ALL, 'section': ALL,
                    'key': ALL, 'subindex': ALL
                },
                'data'
            ),
            staleness_update = Input('staleness-update-trigger', 'data'),
            active_project_id = Input('active-project-id', 'data'),
        ),
        prevent_initial_call = False, # Want to trigger as we change page
    )
    def update_staleness_feedback(
        active_project_id,
        **kwargs
    ):
        """
        Show whether results are up to date with their inputs: per page section
        in the staleness indicators, and per configuration in the section headers.
        """
        groups = ctx.outputs_grouping
        indicator_ids = [x['id'] for x in groups['indicator_class']]
        header_ids = [x['id'] for x in groups['header_class']]
        if not active_project_id or not (indicator_ids or header_ids):
            raise PreventUpdate
        t0 = time.perf_counter()

        logger.debug('Getting lightweight project - Updating staleness feedback')
        lproj = app.project_provider.get_lightweight_project(active_project_id)

        indicator_class, tooltip_children = [], []
        for indicator_id in indicator_ids:
            class_name, text = staleness.indicator_feedback(lproj, indicator_id['process'])
            indicator_class.append(class_name)
            tooltip_children.append(text)

        header_class = []
        if header_ids:
            states = staleness.get_process_states(lproj.metamodels, 'deterministic')
            for header_id in header_ids:
                header_class.append(
                    staleness.result_header_class_name(
                        states.get(header_id['metamodel']),
                        header_id['metamodel'] == lproj.focussed_metamodel_id,
                    )
                )

        t1 = time.perf_counter()
        logger.info(f'Staleness feedback updated in {t1 - t0:.3f}s')

        return dict(
            indicator_class = indicator_class,
            tooltip_children = tooltip_children,
            header_class = header_class,
        )
