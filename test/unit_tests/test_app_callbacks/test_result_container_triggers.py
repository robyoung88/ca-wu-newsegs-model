"""
Tests of `ids_to_update`, which chooses the result containers and headers to redraw from the triggers
of their callbacks.

Several triggers may fire in one call, such as a post-action trigger and the refill interval after a
run. The callbacks looked only at the first (`ctx.triggered_id`), and then parsed every trigger's id
as a pattern-matching id, so failed on the interval's string id, and on the annual/horizon toggle,
whose id has no section.
"""
import json
import unittest

from newsegsmodelapp.components.callbacks.result_container_callbacks import ids_to_update

def _pattern(type_, section, key, purpose = 'trigger', subindex = 0, supersection = 'deterministic'):
    return {'type': type_, 'purpose': purpose, 'supersection': supersection, 'section': section, 'key': key, 'subindex': subindex}

def _trigger(id_, prop = 'data') -> dict:
    """An entry of `ctx.triggered`, whose prop id is the id (as JSON, if a dictionary) and the property"""
    text = json.dumps(id_, separators = (',', ':'), sort_keys = True) if isinstance(id_, dict) else id_
    return {'prop_id': f'{text}.{prop}', 'value': 1}

TABLES = [
    _pattern('result-table', 'tabledraw', 'table_generation', purpose = 'container'),
    _pattern('result-table', 'tabledraw', 'table_finance', purpose = 'container'),
    _pattern('result-table', 'tabledraw', 'table_postopt_metamodel', purpose = 'container', supersection = 'optim'),
]

def update(*triggers):
    return ids_to_update(list(triggers), TABLES, target_type = 'result-table', target_purpose = 'container')

class TestIdsToUpdate(unittest.TestCase):

    def test_matching_trigger(self):
        ids, options = update(_trigger(_pattern('postaction-trigger', 'tabledraw', 'table_finance')))
        self.assertEqual(ids, [TABLES[1]])
        self.assertEqual(options, set())

    def test_pattern_trigger_with_the_refill_interval(self):
        # After a run: the post-action trigger is first, so `ctx.triggered_id` is a dictionary
        ids, _ = update(
            _trigger(_pattern('postaction-trigger', 'tabledraw', 'table_postopt_metamodel', supersection = 'optim')),
            _trigger('delayed-result-container-refill-interval', 'n_intervals'),
        )
        self.assertEqual(ids, TABLES)

    def test_annual_horizon_toggle(self):
        ids, _ = update(_trigger({'type': 'annual-horizon-toggle', 'page': 'site-config'}, 'value'))
        self.assertEqual(ids, TABLES)
        ids, _ = update(
            _trigger(_pattern('postaction-trigger', 'tabledraw', 'table_finance')),
            _trigger({'type': 'annual-horizon-toggle', 'page': 'site-config'}, 'value'),
        )
        self.assertEqual(ids, TABLES)

    def test_initial_call(self):
        # Dash gives a single trigger with an empty id on the initial call
        ids, _ = update({'prop_id': '.', 'value': None})
        self.assertEqual(ids, TABLES)

    def test_option_change_recorded_with_other_triggers(self):
        option = _pattern('result-table-option', 'tabledraw', 'table_finance', purpose = 'statistic')
        ids, options = update(_trigger(option, 'value'))
        self.assertEqual(ids, [TABLES[1]])
        self.assertEqual(options, {('tabledraw', 'table_finance')})
        # With a trigger redrawing everything, the change is still recorded
        ids, options = update(_trigger(option, 'value'), _trigger('delayed-result-container-refill-interval', 'n_intervals'))
        self.assertEqual(ids, TABLES)
        self.assertEqual(options, {('tabledraw', 'table_finance')})

    def test_several_matching_triggers(self):
        ids, _ = update(
            _trigger(_pattern('postaction-trigger', 'tabledraw', 'table_finance')),
            _trigger(_pattern('postaction-trigger', 'tabledraw', 'table_generation')),
            _trigger(_pattern('postaction-trigger', 'tabledraw', 'table_finance', subindex = 1)),
        )
        # Each once, in the order of the targets
        self.assertEqual(ids, [TABLES[0], TABLES[1]])

    def test_headers(self):
        headers = [_pattern('result-section-header', 'tabledraw', 'table_finance', purpose = 'header')]
        ids, _ = ids_to_update(
            [_trigger(_pattern('postaction-trigger', 'tabledraw', 'table_finance')),
             _trigger('delayed-result-container-refill-interval', 'n_intervals')],
            headers, target_type = 'result-section-header', target_purpose = 'header',
        )
        self.assertEqual(ids, headers)
