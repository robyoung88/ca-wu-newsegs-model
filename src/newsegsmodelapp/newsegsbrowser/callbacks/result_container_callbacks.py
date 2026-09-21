
import json
from typing import Any

from dash import ALL, MATCH, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate
from dash_extensions import Purify

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
        print(f'Updating result container {container_id}')
        if active_project_id is None:
            raise PreventUpdate

        # Do not update layout if only redrawing the existing project
        triggered_id = ctx.triggered_id
        is_project_trigger = (triggered_id == 'active-project-id')
        project_has_changed = (active_project_id != last_rendered_project_id)
        if is_project_trigger and not project_has_changed:
            raise PreventUpdate

        app_state = json.loads(app_state) if app_state else {}
                
        section = container_id.get('section')
        key_ = container_id.get('key')
        selected_model = app_state.get('selected_model', 'default')

        if not key_ or not section:
            raise PreventUpdate

        try:
            content_creator = get_result_container_content_creator(
                key_, section, selected_model
            )
        except KeyError as e:
            print('Content creator not found for ', str(container_id))
            print(e)
            return [], active_project_id
        if content_creator is None:
            print('Content creator not found for ', str(container_id))
            return [], active_project_id

        return content_creator(active_project_id, app.project_provider), active_project_id

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
        app_state,
        container_ids,
    ):
        print(f'Updating header {container_ids}')
        if active_project_id is None or container_ids is None or not len(container_ids):
            raise PreventUpdate

        ann_hori_toggle = ann_hori_toggle[0] if len(ann_hori_toggle) else False
        return_headers: list[Any] = [no_update] * len(container_ids)
        contents_by_section = {}

        app_state = json.loads(app_state) if app_state else {}
        selected_model = app_state.get('selected_model', 'default')
        for idx, cid in enumerate(container_ids):
            section = cid.get('section')
            if section in contents_by_section:
                return_headers[idx] = contents_by_section[section]
                continue

            key = cid.get('key')
            if not section or not key:
                continue

            content_creator = get_result_section_header_content_creator(
                key, section, selected_model
            )
            if content_creator is None:
                continue
            contents = content_creator(
                active_project_id, app.project_provider, app.results_provider, ann_hori_toggle
            )
            contents_by_section[section] = contents
            return_headers[idx] = contents

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
        Input('active-project-id', 'data'),
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
        prevent_initial_call = True
    )
    def update_result_section_contents(
        postaction_triggers,
        result_table_options,
        ann_hori_toggle,
        active_project_id,
        app_state,
        container_ids,
        option_ids,
        rendered_project_ids,
        rendered_project_table_revision,
        rendered_ann_hori_state,
    ):
        print(f'Updating results {container_ids}')
        if active_project_id is None or container_ids is None or not len(container_ids):
            raise PreventUpdate

        # Do not update if the toggle status has not changed, the project is the same,
        # and the table revision number is the same.
        
        proj = app.project_provider.get_project(active_project_id)
        table_rev = proj.table_config.revision
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

        app_state = json.loads(app_state) if app_state else {}
        selected_model = app_state.get('selected_model', 'default')

        table_options = {}
        for optid, optval in zip(option_ids, result_table_options):
            table_options[optid['purpose']] = optval

        print('TABLE OPTIONS')
        print(table_options)

        for idx, cid in enumerate(container_ids):
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
                table_getter = registers.get_table_getter(table_name, selected_model)
            except KeyError:
                pass
            if table_getter is not None:
                print(f'Found getter for {table_name}')
                table_options['ann_hori_toggle'] = ann_hori_toggle
                table_options['subindex'] = subindex
                res, rev = table_getter(active_project_id, table_options, app.project_provider, app.results_provider)
            else:
                if subindex > 0:
                    subindex_map = registers.get_table_subindex_map(key, selected_model)
                    if subindex_map:
                        table_name = subindex_map[subindex]
                
                sub_table_name = table_name + '_hori' if ann_hori_toggle else table_name + '_ann'
                print (f'getting from table {sub_table_name} - subindex is {subindex}')
                res, rev = app.results_provider.get_result(sub_table_name, proj.table_config)
                if res is None:
                    # Retry without the subtable
                    print (f'getting from table {table_name} - subindex is {subindex}')
                    res, rev = app.results_provider.get_result(table_name, proj.table_config)

            print(type(res))
            if isinstance(res, list):
                if ann_hori_toggle:
                    res = Purify(html =res[1])
                else:
                    res = Purify(html=res[0])

            print(type(res))

            # TODO: Feedback if result is stale
            if res is not None:
                contents_by_section_subindex[ss] = [res]
                return_contents[idx] = [res]
                return_is_stale[idx] = rev != proj.table_config.revision
                return_rendered_project_table_revision[idx] = rev

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
        print(f'Updating figures {container_ids}')
        if active_project_id is None or container_ids is None or not len(container_ids):
            raise PreventUpdate
        
        proj = app.project_provider.get_project(active_project_id)
        table_rev = proj.table_config.revision
        ann_hori_toggle = ann_hori_toggle[0] if len(ann_hori_toggle) else False

        return_contents: list[Any] = [no_update] * len(container_ids)

        contents_by_section_subindex = {}

        app_state = json.loads(app_state) if app_state else {}
        selected_model = app_state.get('selected_model', 'default')

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
                figure_getter = registers.get_table_getter(table_name, selected_model)
            except KeyError:
                continue
            if figure_getter is not None:
                table_options['ann_hori_toggle'] = ann_hori_toggle
                table_options['subindex'] = subindex
                res, rev = figure_getter(active_project_id, table_options, app.project_provider, app.results_provider)
            
            if res is not None:
                contents_by_section_subindex[ss] = res
                return_contents[idx] = res

        return return_contents 
        
    @app.callback(
        Output({'type': 'resize-handle', 'page': ALL}, 'className'),
        Output({'type': 'result-tooltip', 'page': ALL}, 'children'),

        Input({
            'type': 'result-table', 'purpose': 'container',
            'supersection': ALL, 'section': ALL,
            'key': ALL, 'subindex': ALL
        }, 'data-is-stale'),

        Input({
            'type': 'input-group-config-update-trigger', 
            'supersection': ALL, 'purpose': 'trigger',
            'section': ALL, 'key': ALL, 'subindex': ALL,
            'parameter_index': ALL, 'vector_location': ALL,
        }, 'data'),

        State('active-project-id', 'data'),
        State({
            'type': 'result-table', 'purpose': 'container',
            'supersection': ALL, 'section': ALL,
            'key': ALL, 'subindex': ALL
        }, 'data-rendered-project-id'),
        State({
            'type': 'result-table', 'purpose': 'container',
            'supersection': ALL, 'section': ALL,
            'key': ALL, 'subindex': ALL
        }, 'data-rendered-project-table-revision'),

        State({'type': 'resize-handle', 'page': ALL}, 'className'),
        State({'type': 'result-tooltip', 'page': ALL}, 'children'),
    )
    def update_stale_indicators(
        data_stale,
        config_update,
        active_project_id,
        rendered_project_ids,
        rendered_project_table_revisions,
        handle_ids,
        tooltip_ids,
    ):
        triggered_id = ctx.triggered_id
        print(f'checking staleness - triggered by {triggered_id}')
        if isinstance(triggered_id, dict) and triggered_id['type'] == 'input-group-config-update-trigger':
            proj = app.project_provider.get_project(active_project_id)
            results_stale = False
            # Because have retrieved the proj from database, will never be modified.
            #results_stale = proj.table_config.chain_modified or any(x.modified for x in proj._variables_by_uid.values())
            if not results_stale:
                results_stale = not all(x is not None and x == active_project_id for x in rendered_project_ids)
            if not results_stale:
                table_revision = proj.table_config.revision
                results_stale = not all(x is not None and x == table_revision for x in rendered_project_table_revisions)
        else:
            if data_stale is None:
                raise PreventUpdate
            results_stale = any(x for x in data_stale)

        if results_stale:
            handle_class = 'resize-handle resize-handle-warning'
            tooltip_text = 'Results require refreshing.'
        else:
            handle_class = 'resize-handle resize-handle-ok'
            tooltip_text = 'Results up to date.'

        return [handle_class] * len(handle_ids), [tooltip_text] * len(tooltip_ids)
