"""Callbacks which fill the containers of results, in the sections registered for the model type, when results become available.
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


_UPDATE_ALL_TRIGGER_TYPES = {'annual-horizon-toggle'}
"""Types of the triggers which change every result, so that all are redrawn."""

REFILL_INTERVAL_ID = 'delayed-result-container-refill-interval'
"""The interval which refills the result tables after a change of project: reset to 0, then ticks to 1."""

EMPTY_FIGURE = {'data': [], 'layout': {}}
"""What a result figure shows when there is no result, as when the page is first drawn."""

def ids_to_update(
    triggered: list[dict],
    target_ids: list[dict],
    target_type: str,
    target_purpose: str,
) -> tuple[list[dict], set[tuple[str, str]]]:
    """The ids of the result containers or headers to redraw for the triggers of a callback.

    Every trigger is considered, as several may fire together, such as a post-action trigger and the
    refill interval after a run (see `callback_utils.ids_to_update`). The annual/horizon toggle
    redraws every target.

    Args:
        triggered: `ctx.triggered`.
        target_ids: The ids of the containers or headers of the callback.
        target_type: Type of the ids of the targets, e.g. 'result-table'.
        target_purpose: Purpose of the ids of the targets, e.g. 'container'.

    Returns:
        The ids to redraw, and the (section, key) of each table whose options were changed.
    """
    triggers = callback_utils.get_triggers(triggered)
    option_changed = {
        (x.id['section'], x.id['key']) for x in triggers # pyright: ignore[reportIndexIssue, reportCallIssue, reportArgumentType]
        if x.type == 'result-table-option' and 'section' in x.id and 'key' in x.id
    }
    ids = callback_utils.ids_to_update(
        triggers, target_ids, target_type, target_purpose, update_all_types = _UPDATE_ALL_TRIGGER_TYPES
    )
    return ids, option_changed

def result_table_triggers(triggered: list[dict]) -> list[dict] | None:
    """The triggers of the result tables callback to act on: all but the refill interval, unless it ticks to 1.

    The interval is reset to 0 on a change of project and ticks to 1 after, so only the tick redraws. Other
    triggers which fire with the reset (such as post-action triggers) are still acted on.

    Args:
        triggered: `ctx.triggered`.

    Returns:
        The entries of `ctx.triggered` to act on (an empty list on the initial call, which redraws every table), or
        None if there is nothing to act on.
    """
    kept = []
    initial_call = True
    for entry in triggered:
        id_, _ = callback_utils.parse_prop_id(entry.get('prop_id', '.'))
        if id_ is None:
            continue
        initial_call = False
        if id_ == REFILL_INTERVAL_ID and entry.get('value') != 1:
            continue
        kept.append(entry)
    if initial_call:
        return []
    return kept or None

def only_project_changed(triggers: list[callback_utils.Trigger]) -> bool:
    """Whether the active project is the only trigger of the result containers callback.

    Then only the containers drawn for another project are redrawn. A change of page or layout, alone or with the
    project, redraws every container.

    Args:
        triggers: The triggers of the callback.

    Returns:
        Whether only the active project triggered the callback.
    """
    return bool(triggers) and all(x.id == 'active-project-id' for x in triggers)

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
        is_project_trigger = only_project_changed(callback_utils.get_triggers())

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

        headers_for_update, _ = ids_to_update(
            ctx.triggered,
            [x['id'] for x in ctx.outputs_grouping['containers']],
            target_type = 'result-section-header',
            target_purpose = 'header',
        )

        if not headers_for_update:
            return rval

        app_state = json.loads(app_state) if app_state else {}
        model_type = app_state.get('model_type', 'default')

        # Headers of the same section and key (e.g. on different pages) share their contents
        contents_by_section_key = {}
        ann_hori_toggle = ann_hori_toggle[0] if len(ann_hori_toggle) else False

        for container_id in headers_for_update:
            section = container_id['section']
            key = container_id['key']
            if (section, key) in contents_by_section_key:
                callback_utils.update_property_by_id(
                    container_id,
                    'children',
                    contents_by_section_key[(section, key)],
                    rval
                )
                continue
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
            contents_by_section_key[(section, key)] = contents
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
            data_rendered_metamodel_id = Output({
                'type': 'result-table', 'purpose': 'container',
                'supersection': ALL, 'section': ALL,
                'key': ALL, 'subindex': ALL
            }, 'data-rendered-metamodel-id'),
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
            rendered_metamodel_ids =  State({
                'type': 'result-table', 'purpose': 'container',
                'supersection': ALL, 'section': ALL,
                'key': ALL, 'subindex': ALL
            }, 'data-rendered-metamodel-id'),
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
        rendered_metamodel_ids,
        **kwargs
    ):
        if active_project_id is None or container_ids is None or not len(container_ids):
            raise PreventUpdate

        # The interval is reset to 0 on project change and then ticks to 1; only act on the tick
        triggered = result_table_triggers(ctx.triggered)
        if triggered is None:
            raise PreventUpdate

        t0 = time.perf_counter()
        rval = callback_utils.create_noupdate_return()

        # Tables whose options were changed must be redrawn even if the revision is unchanged
        tables_for_update, option_changed_tables = ids_to_update(
            triggered,
            [x['id'] for x in ctx.outputs_grouping['table']],
            target_type = 'result-table',
            target_purpose = 'container',
        )
        if not tables_for_update:
            return rval

        # Tables whose post-action trigger fired: their results have just been saved
        result_saved_tables = {
            (x.id['section'], x.id['key']) for x in callback_utils.get_triggers(triggered) # pyright: ignore[reportIndexIssue, reportCallIssue, reportArgumentType]
            if x.type == 'postaction-trigger'
        }

        app_state = json.loads(app_state) if app_state else {}
        model_type = app_state.get('model_type', 'default')

        contents_by_section_subindex = {}
        """
        Local store for contents to prevent redrawing within single call, keyed
        by (section, key, subindex): containers share a section ('tabledraw'),
        so the key is needed to tell their tables apart
        """
        
        # Do not update if the toggle status has not changed, the project is the same,
        # and the table drawn is of the project's table revision.
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
        rendered_metamodel = {
            (k['section'], k['key']) : v for k, v in zip(container_ids, rendered_metamodel_ids)
        }

        options_per_table = {}
        for id, val in zip(table_options['ids'], table_options['values']):
            lookup = (id['section'], id['key'])
            options_per_table.setdefault(lookup, {})[id['purpose']] = val

        for container_id in tables_for_update:
            section = container_id['section']
            key = container_id['key']
            lookup = (section, key)

            # Find any custom table providers for this table / model
            table_getter = None
            try:
                table_getter = registers.get_table_getter(key, model_type)
            except KeyError:
                pass

            # A getter may read results saved at a revision other than the project's (a configuration's), or saved
            # again at the same one (a DSA run again with other bounds), so the revision recorded doesn't show
            # that its table is still the one drawn: draw it whenever its results have just been saved (#206)
            getter_result_saved = table_getter is not None and lookup in result_saved_tables
            if not getter_result_saved and lookup not in option_changed_tables and rendered_ann_hori_state.get(lookup) is not None and rendered_ann_hori_state[lookup] == ann_hori_toggle:
                if rendered_project.get(lookup) is not None and rendered_project[lookup] == active_project_id:
                    if rendered_revision.get(lookup) is not None and rendered_revision[lookup] == table_rev:
                        # A getter may read the focussed configuration's results, and a change of focus keeps the
                        # project and its revision (#187); the conventional lookup reads the project's
                        if table_getter is None or rendered_metamodel.get(lookup) == lproj.focussed_metamodel_id:
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
                    contents_by_section_subindex[ss][2], rval
                )
                callback_utils.update_property_by_id(
                    container_id, 'data-rendered-ann-hori-state',
                    ann_hori_toggle, rval
                )
                callback_utils.update_property_by_id(
                    container_id, 'data-rendered-metamodel-id',
                    lproj.focussed_metamodel_id, rval
                )
                continue

            opts = options_per_table.get(lookup, {})

            table_name = key
            # 1) Use any custom table provider found above
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
                # The revision of the table drawn is recorded, not the project's, so that a stale table is drawn again
                # once the table of the current revision is saved (#195)
                contents_by_section_subindex[ss] = res, stale, rev
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
                    rev, rval
                )
                callback_utils.update_property_by_id(
                    container_id, 'data-rendered-ann-hori-state',
                    ann_hori_toggle, rval
                )
                callback_utils.update_property_by_id(
                    container_id, 'data-rendered-metamodel-id',
                    lproj.focussed_metamodel_id, rval
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
            else:
                # Figures can't record what they were drawn for: the one shown may be of another configuration (#187)
                return_contents[idx] = EMPTY_FIGURE
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
