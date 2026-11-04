"""
A test that every row of every registered input container can reach `react_to_input_change`.

The Dash renderer only calls a pattern-matching callback for a row (the values of its `MATCH` keys) that has a component
matching the callback's first output. A row with an input of the callback but no such component is silently never
handled: nothing is sent when the input changes. Rows built with `create_lazy_input_details` carry a hidden anchor for
this; other rows have their `single-input-config` inputs.

Only what the content creators render for each model type's new project is checked: rows drawn by other callbacks, or
present only in other states of a project, are not.
"""
from collections import defaultdict

from newsegsmodelapp import registers
from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

from .base import InputChangeTestCase
from .dash_dispatch import INPUT_CHANGE_OUTPUT, _matches, get_callback_spec, render_input_containers

class TestRowAnchors(InputChangeTestCase):
    """Every row with an input of `react_to_input_change` has a component matching its first output"""

    def test_every_row_has_anchor(self):
        spec = get_callback_spec(self.client, *INPUT_CHANGE_OUTPUT)
        first_output = spec.outputs[0][0]
        match_keys = [k for k, v in first_output.items() if v == ['MATCH']]
        input_patterns = [x for x, _ in spec.inputs if isinstance(x, dict)]

        containers = sorted({(supersection, section) for supersection, section, _ in registers.INPUT_CONTAINER_CONTENT_CREATORS})
        for model_type, factory in PROJECT_FACTORIES.items():
            project = factory()
            self.reader.add_component(project)
            for supersection, section in containers:
                # As the app chooses the creator, with the fallbacks
                section = None if section == 'ALL' else section
                with self.subTest(model_type = model_type, supersection = supersection, section = section):
                    components = render_input_containers(self.provider, project.id, [(supersection, section)], model_type)

                    rows = defaultdict(list)
                    for c in components:
                        if set(match_keys) <= set(c.id):
                            rows[tuple(c.id[k] for k in match_keys)].append(c.id)

                    unreachable = {
                        row: id_ for row, ids in rows.items() for id_ in ids
                        if any(_matches(p, id_, id_) for p in input_patterns)
                        and not any(_matches(first_output, x, id_) for x in ids)
                    }
                    self.assertEqual(unreachable, {}, 'Rows with an input but no component matching the first output')
