import logging
logger = logging.getLogger(__name__)

import json
import time
from typing import Any, cast

from dash import ALL, MATCH, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate
from dash_extensions import Purify

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.components import callback_utils
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
        Output({
            'type': 'result-container', 'purpose': 'container',
            'supersection': MATCH, 'section': MATCH,
            'key': MATCH, 'subindex': MATCH
        }, 'children'),
        Output({
            'type': 'result-container', 'purpose': 'container',
            'supersection': MATCH, 'section': MATCH,
            'key': MATCH, 'subindex': MATCH
        }, 'data-rendered-project-id'),

        Input('url', 'pathname'),
        Input('layout-update-trigger', 'data'),
        Input('active-project-id', 'data'),

        State('app-state', 'data'),
        State({
            'type': 'result-container', 'purpose': 'container',
            'supersection': MATCH, 'section': MATCH,
            'key': MATCH, 'subindex': MATCH
        }, 'id'),
        State({
            'type': 'result-container', 'purpose': 'container',
            'supersection': MATCH, 'section': MATCH,
            'key': MATCH, 'subindex': MATCH
        }, 'data-rendered-project-id'),
        prevent_initial_call = True
    )
    def update_output_container_contents(
        page_change_trigger,
        layout_update_trigger,
        active_project_id,
        app_state,
        container_id,
        last_rendered_project_id,
    ):
        if active_project_id is None:
            raise PreventUpdate
        t0 = time.perf_counter()

        # Do not update layout if only redrawing the existing project
        triggered_id = ctx.triggered_id
        is_project_trigger = (triggered_id == 'active-project-id')
        project_has_changed = (active_project_id != last_rendered_project_id)
        if is_project_trigger and not project_has_changed:
            raise PreventUpdate
        app_state = json.loads(app_state) if app_state else {}

        section = container_id.get('section')
        key_ = container_id.get('key')
        model_type = app_state.get('model_type', 'default')

        if not key_ or not section:
            raise PreventUpdate

        def _not_found():
            logger.exception(
                'Result container content creator not found for Container ID: %s',
                container_id
            )
            return [], active_project_id

        try:
            content_creator = get_result_container_content_creator(
                key_, section, model_type
            )
        except KeyError as e:
            return _not_found()
        if content_creator is None:
            return _not_found()

        logger.debug(
            'Creating Result Container contents using creator found for %s.%s.%s',
            key_, section, model_type
        )
        cc = content_creator(active_project_id, app.project_provider), active_project_id
        t1 = time.perf_counter()
        logger.info(f'Result Container for {section}, {key_} created in {t1 - t0:.3f}s')
        return cc

    @app.callback(
        Output({
            'type': 'result-section-header', 'purpose': 'header',
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'children'),

        Input({
            'type': 'postaction-trigger', 'purpose': 'trigger',
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'data'),

        Input({'type': 'annual-horizon-toggle', 'page': ALL}, 'value'),
        Input('active-project-id', 'data'),
        Input('trigger-check-stale', 'data'),
        State('app-state', 'data'),

        State({
            'type': 'result-section-header', 'purpose': 'header',
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'id'),
    )
    def update_result_section_header_contents(
        postaction_triggers,
        ann_hori_toggle,
        active_project_id,
        check_stale,
        app_state,
        container_ids,
    ):
        if active_project_id is None or container_ids is None or not len(container_ids):
            raise PreventUpdate
        t0 = time.perf_counter()

        logger.debug(
            'Updating Result Section Header for Section = %s, Key = %s; Triggered by: %s;',
            container_ids[0]['section'], container_ids[0]['key'], ctx.triggered_id
        )

        ann_hori_toggle = ann_hori_toggle[0] if len(ann_hori_toggle) else False
        return_headers: list[Any] = [no_update] * len(container_ids)
        contents_by_section = {}

        app_state = json.loads(app_state) if app_state else {}
        model_type = app_state.get('model_type', 'default')
        for idx, cid in enumerate(container_ids):
            section = cid.get('section')
            if section in contents_by_section:
                return_headers[idx] = contents_by_section[section]
                continue

            key = cid.get('key')
            if not section or not key:
                continue

            content_creator = get_result_section_header_content_creator(
                key, section, model_type
            )
            if content_creator is None:
                continue
            logger.debug(
                'Creating Result Section Header contents using creator found for %s.%s.%s',
                key, section, model_type
            )
            contents = content_creator(
                active_project_id, app.project_provider, app.results_provider, ann_hori_toggle
            )
            contents_by_section[section] = contents
            return_headers[idx] = contents

        t1 = time.perf_counter()
        logger.info(f'Result Section Header for {container_ids[0]['section']}, {container_ids[0]['key']} created in {t1 - t0:.3f}s')

        return return_headers

    @app.callback(
        Output({
            'type': 'result-table', 'purpose': 'container',
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'children'),
        Output({
            'type': 'result-table', 'purpose': 'container',
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'data-is-stale'),
        Output({
            'type': 'result-table', 'purpose': 'container',
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'data-rendered-project-id'),
        Output({
            'type': 'result-table', 'purpose': 'container',
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'data-rendered-project-table-revision'),
        Output({
            'type': 'result-table', 'purpose': 'container',
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'data-rendered-ann-hori-state'),

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
        Input('delayed-result-container-refill-interval', 'n_intervals'),
        State('active-project-id', 'data'),
        State('app-state', 'data'),

        State({
            'type': 'result-table', 'purpose': 'container',
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'id'),
        State({
            'type': 'result-table-option', 'purpose': ALL,
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'id'),
        State({
            'type': 'result-table', 'purpose': 'container',
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'data-rendered-project-id'),
        State({
            'type': 'result-table', 'purpose': 'container',
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'data-rendered-project-table-revision'),
        State({
            'type': 'result-table', 'purpose': 'container',
            'supersection': ALL, 'section': MATCH,
            'key': MATCH, 'subindex': ALL
        }, 'data-rendered-ann-hori-state'),
        #prevent_initial_call = True
    )
    def update_result_section_contents(
        postaction_triggers,
        result_table_options,
        ann_hori_toggle,
        result_interval_count,
        active_project_id,
        app_state,
        container_ids,
        option_ids,
        rendered_project_ids,
        rendered_project_table_revision,
        rendered_ann_hori_state,
    ):
        if active_project_id is None or container_ids is None or not len(container_ids):
            raise PreventUpdate

        trig = ctx.triggered_id
        if isinstance(trig, str) and trig == 'result-container-refill-interval':
            if callback_utils.get_triggered_value() != 1:
                raise PreventUpdate

        t0 = time.perf_counter()

        # Do not update if the toggle status has not changed, the project is the same,
        # and the table revision number is the same.
        logger.debug(
            'Getting lightweight project - Updating Result Table Containers [Section = %s, Key = %s]', 
            container_ids[0]['section'], container_ids[0]['key']
        )
        lproj = app.project_provider.get_lightweight_project(active_project_id)
        table_rev = lproj.table_config.revision
        ann_hori_toggle = ann_hori_toggle[0] if len(ann_hori_toggle) else False
        if all(x is not None and x == ann_hori_toggle for x in rendered_ann_hori_state):
            if all(x is not None and x == active_project_id for x in rendered_project_ids):
                if all(x is not None and x==table_rev for x in rendered_project_table_revision):
                    raise PreventUpdate

        return_contents: list[Any] = [no_update] * len(container_ids)
        return_is_stale: list[Any] = [no_update] * len(container_ids)
        return_rendered_project_id = [active_project_id] * len(rendered_project_ids)
        return_rendered_project_table_revision = [table_rev] * len(rendered_project_table_revision)
        return_ann_hori_state = [ann_hori_toggle] * len(rendered_ann_hori_state)

        contents_by_section_subindex = {}
        """Local store for contents to prevent redrawing within single call"""

        app_state = json.loads(app_state) if app_state else {}
        model_type = app_state.get('model_type', 'default')

        table_options = {}
        for optid, optval in zip(option_ids, result_table_options):
            table_options[optid['purpose']] = optval

        for idx, cid in enumerate(container_ids):

            # Check if already drawn
            section = cid.get('section')
            subindex = int(cid.get('subindex'))
            ss = (section, subindex)
            if ss in contents_by_section_subindex:
                return_contents[idx] = contents_by_section_subindex[ss]
                continue

            key = cid.get('key')
            if not section or not key:
                continue

            # Find any custom table providers for this table / model
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
                table_options['ann_hori_toggle'] = ann_hori_toggle
                table_options['subindex'] = subindex
                res, rev = table_getter(
                    active_project_id, table_options, app.project_provider, app.results_provider
                )

            else:
                # Conventional table lookup
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

            # TODO: Feedback if result is stale
            if res is not None:
                logger.debug(
                    'Table found is for revision %d; Current project table revision is %d. Result Table Container Section: %s; Subindex: %s; Key: %s;',
                    rev, lproj.table_config.revision, section, subindex, key
                )
                contents_by_section_subindex[ss] = [res]
                return_contents[idx] = [res]
                return_is_stale[idx] = rev != lproj.table_config.revision
                return_rendered_project_table_revision[idx] = rev
            else:
                logger.debug(
                    'Table not found for Result Table Container: Section: %s; Subindex: %s; Key: %s;',
                    section, subindex, key
                )
                contents_by_section_subindex[ss] = []
                return_contents[idx] = []
                return_is_stale[idx] = True
                return_rendered_project_table_revision[idx] = -1

        t1 = time.perf_counter()
        logger.info(f'Result Table for {section}, {subindex}, {key} created in {t1 - t0:.3f}s')

        return (
            return_contents, 
            return_is_stale, 
            return_rendered_project_id, 
            return_rendered_project_table_revision, 
            return_ann_hori_state
        )

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
        
    # @app.callback(
    #     output = dict(
    #         indicator_class = Output(
    #             {'type': 'resize-handle', 'page': ALL},
    #             'className',
    #         ),
    #         tooltip_children = Output(
    #             {'type': 'result-tooltip', 'page': ALL}, 
    #             'children',
    #         ),
    #         trigger_check_stale_data = Output(
    #             'trigger-check-stale', 'data'
    #         ),
    #     ),
    #     inputs = dict(
    #         data_stale = Input(
    #             {
    #                 'type': 'result-table', 'purpose': 'container',
    #                 'supersection': ALL, 'section': ALL,
    #                 'key': ALL, 'subindex': ALL
    #             }, 
    #             'data-is-stale',
    #         ),
    #         config_update = Input(
    #             {
    #                 'type': 'input-group-config-update-trigger', 
    #                 'supersection': ALL, 'purpose': 'trigger',
    #                 'section': ALL, 'key': ALL, 'subindex': ALL,
    #                 'parameter_index': ALL, 'vector_location': ALL,
    #             }, 
    #             'data'
    #         ),
    #     ),
    #     state = dict(
    #         active_project_id = State('active-project-id', 'data'),
    #         rendered_project_ids = State(
    #             {
    #                 'type': 'result-table', 'purpose': 'container',
    #                 'supersection': ALL, 'section': ALL,
    #                 'key': ALL, 'subindex': ALL
    #             }, 
    #             'data-rendered-project-id'
    #         ),
    #         rendered_project_table_revisions = State(
    #             {
    #                 'type': 'result-table', 'purpose': 'container',
    #                 'supersection': ALL, 'section': ALL,
    #                 'key': ALL, 'subindex': ALL
    #             },
    #             'data-rendered-project-table-revision'
    #         ),
    #         trigger_ids = State(
    #             {
    #                 'type': 'postaction-trigger', 'purpose': 'trigger',
    #                 'supersection': ALL, 'section': ALL,
    #                 'key': ALL, 'subindex': ALL
    #             },
    #             'id'
    #         ),
    #         #indicator_class = State({'type': 'resize-handle', 'page': ALL}, 'className'),
    #         #tooltip_children = State({'type': 'result-tooltip', 'page': ALL}, 'children'),
    #     ),
    # )
    # def update_stale_indicators(
    #     data_stale,
    #     config_update,
    #     active_project_id,
    #     rendered_project_ids,
    #     rendered_project_table_revisions,
    #     #indicator_class,
    #     #tooltip_children,
    #     **kwargs
    # ):
    #     triggered_id = ctx.triggered_id
    #     t0 = time.perf_counter()
    #     logger.debug('Checking staleness - triggered by %s', triggered_id)
    #     if triggered_id is None:
    #         raise PreventUpdate
    #     elif isinstance(triggered_id, dict) and triggered_id['type'] == 'input-group-config-update-trigger':
    #         provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)
    #         logger.debug('Getting lightweight project - Checking Staleness')
    #         lproj = provider.get_lightweight_project(active_project_id)
            
    #         results_stale = False
    #         # Because have retrieved the proj from database, will never be modified.
    #         #results_stale = proj.table_config.chain_modified or any(x.modified for x in proj._variables_by_uid.values())
    #         if not results_stale:
    #             results_stale = not all(x is not None and x == active_project_id for x in rendered_project_ids)
    #         if not results_stale:
    #             table_revision = lproj.table_config.revision
    #             logger.debug(
    #                 'Checking against project table revision: %s', table_revision
    #             )
    #             logger.debug(
    #                 'Rendered table revisions are: %s', rendered_project_table_revisions
    #             )
    #             results_stale = not all(x is not None and x == table_revision for x in rendered_project_table_revisions)
                
    #     else:
    #         if data_stale is None:
    #             raise PreventUpdate
    #         logger.debug(
    #             'Checking against data-is-stale: %s', data_stale
    #         )
    #         results_stale = any(x for x in data_stale)

    #     rval = callback_utils.create_noupdate_return()

    #     if results_stale:
    #         handle_class = 'resize-handle resize-handle-warning'
    #         tooltip_text = 'Results require refreshing.'
    #     else:
    #         handle_class = 'resize-handle resize-handle-ok'
    #         tooltip_text = 'Results up to date.'

    #     rval['indicator_class'] = [handle_class] * len(rval['indicator_class'])
    #     rval['tooltip_children'] = [tooltip_text] * len(rval['tooltip_children'])
    #     rval['trigger_check_stale_data'] = time.time_ns()

    #     t1 = time.perf_counter()
    #     logger.info(f'Staleness checked in {t1 - t0:.3f}s')

    #     return rval

    # @app.callback(
    #     output = dict(
    #         header_classnames = Output(
    #             {
    #                 'type': 'result-header-single-config',
    #                 'table': ALL,
    #                 'metamodel': ALL,
    #             },
    #             'className'
    #         )
    #     ),
    #     inputs = dict(
    #         trigger_check_stale = Input(
    #             'trigger-check-stale', 'data'
    #         )
    #     ),
    #     state = dict(
    #         headers = dict(
    #             parent_component = State(
    #                 {
    #                     'type': 'result-header-single-config',
    #                     'table': ALL,
    #                     'metamodel': ALL,
    #                 },
    #                 'data-parent-component'
    #             ),
    #             parent_component_revision = State(
    #                 {
    #                     'type': 'result-header-single-config',
    #                     'table': ALL,
    #                     'metamodel': ALL,
    #                 },
    #                 'data-parent-component-revision'
    #             ),
    #             class_name = State(
    #                 {
    #                     'type': 'result-header-single-config',
    #                     'table': ALL,
    #                     'metamodel': ALL,
    #                 },
    #                 'className'
    #             ),
    #             id = State(
    #                 {
    #                     'type': 'result-header-single-config',
    #                     'table': ALL,
    #                     'metamodel': ALL,
    #                 },
    #                 'id'
    #             )
    #         )
    #     ),
    #     prevent_initial_call = True
    # )
    # def update_result_header_staleness(
    #     headers, **kwargs
    # ):
    #     component_ids = list(set(headers['parent_component']))
    #     current_revisions = app.project_provider._component_provider.get_component_metadata(
    #         component_ids,
    #         'revision'
    #     )

    #     rval = []
    #     for parent_component, parent_revision, cn, id in zip(headers['parent_component'], headers['parent_component_revision'], headers['class_name'], headers['id']):
    #         r0 = -1 if parent_revision is None else int(parent_revision)
    #         r1 = int(current_revisions[parent_component]['revision'])
    #         logger.debug(
    #             'Checking staleness for Result Header ID: %s; Drawn: %d; Live: %d; Component ID: %s',
    #             id, r0, r1, parent_component
    #         )
    #         if r0 != r1:
    #             if not 'stale' in cn:
    #                 cn = (cn + ' stale').strip()
    #         else:
    #             if 'stale' in cn:
    #                 cn = cn.replace(' stale', '').strip()
    #         rval.append(cn)
        
    #     return dict(header_classnames = rval)
