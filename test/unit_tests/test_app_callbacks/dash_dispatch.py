"""
Dispatch of requests to Dash callbacks through the Flask test client, as the browser makes them.

A request is posted to `/_dash-update-component`, so that Dash itself resolves the callback, its pattern matching,
`ctx`, the grouping of its outputs and `no_update`. The specification of the callback (the order of its inputs,
outputs and state) is read from `/_dash-dependencies` rather than written here, so the helper follows changes to the
callback.

The browser sends, for each wildcard input, output and state, the components on the page that match it. Here, the page
is a list of Dash components: those rendered by the app's input container content creators (`render_input_containers`),
optionally with others added by a test. The values sent are the components' properties, except that of the trigger.

Usage:

    page = render_input_containers(app.project_provider, project.id, [('deterministic', 'gen_input')])
    response = dispatch_input_change(
        client,
        trigger = variable_id('single-input-config', 'parameter', 'gen_input', 'wind_capacity'),
        value = 12.5,
        project_id = project.id,
        model_type = 'sprake',
        components = page,
    )
    response.updated                                       # False if Dash made no update (status 204)
    response.get(some_id, 'value')                         # the value returned for a component, or NOT_UPDATED
"""
from collections.abc import Iterable
from dataclasses import dataclass, field
import json
from typing import Any

from dash.development.base_component import Component

from newsegsmodelapp.registers import get_input_container_content_creator, get_input_editor_content_creator

DEPENDENCIES_URL = '/_dash-dependencies'
UPDATE_URL = '/_dash-update-component'

# react_to_input_change is the only callback to output the values of `single-input-config` components
INPUT_CHANGE_OUTPUT = ('single-input-config', 'value')

class _NotUpdated:
    def __repr__(self):
        return 'NOT_UPDATED'

NOT_UPDATED = _NotUpdated()
"""Returned by `CallbackResponse.get` for a property that the callback did not update."""

def stringify_id(id_: str | dict) -> str:
    """The id as Dash writes it in requests and responses: JSON with sorted keys and no spaces."""
    if isinstance(id_, dict):
        return json.dumps(id_, sort_keys = True, separators = (',', ':'))
    return id_

def _parse_id(id_: str) -> str | dict:
    return json.loads(id_) if id_.startswith('{') else id_

def variable_id(
    type_: str,
    purpose: str,
    section: str,
    key: str,
    subindex: int | str = 0,
    *,
    supersection: str = 'deterministic',
    parameter_index: int = 0,
    vector_location: int = 0,
) -> dict[str, Any]:
    """The id of a component of a variable parameter, as `VariableInstanceParameterComponentID.as_dict` makes it.

    Args:
        type_: The type field (e.g. `single-input-config`, `input-action-button`).
        purpose: The purpose field (e.g. `parameter`, `value-reset`).
        section: Interface section of the variable.
        key: Interface key of the variable.
        subindex: Interface subindex of the variable.
        supersection: The supersection of the container (e.g. `deterministic`, `dsa`, `optim`).
        parameter_index: Index of the parameter.
        vector_location: Position within an array parameter.

    Returns:
        The id.
    """
    return dict(
        type = type_,
        purpose = purpose,
        supersection = supersection,
        section = section,
        key = key,
        subindex = subindex,
        parameter_index = parameter_index,
        vector_location = vector_location,
    )

def iter_components(layout: Any) -> Iterable[Component]:
    """Every component in a layout (a component, or a list of them), depth first."""
    if isinstance(layout, (list, tuple)):
        for x in layout:
            yield from iter_components(x)
    elif isinstance(layout, Component):
        yield layout
        yield from iter_components(getattr(layout, 'children', None))

def render_input_containers(
    project_provider,
    project_id: str,
    containers: Iterable[tuple[str, str | None]],
    model_type: str = 'sprake',
    open_editors: bool = False,
) -> list[Component]:
    """The components with dictionary ids in input containers, as the app renders them.

    Args:
        project_provider: Provider of the project.
        project_id: Id of the project.
        containers: (supersection, section) of each container, e.g. `('deterministic', 'gen_input')` or
            `('dsa', None)`.
        model_type: The model type, which selects the content creators.
        open_editors: Also build the editor of every row which builds it when opened (see
            `create_lazy_input_details`), as opening each row does: e.g. the DSA rows' inputs.

    Returns:
        The components.
    """
    components = []
    for supersection, section in containers:
        creator = get_input_container_content_creator(supersection, section, model_type)
        content = creator(project_id, project_provider)
        components.extend(x for x in iter_components(content) if isinstance(getattr(x, 'id', None), dict))
    if open_editors:
        for editor in [x for x in components if x.id.get('type') == 'input-group-editor']:
            editor_creator = get_input_editor_content_creator(editor.id['supersection'], editor.id['section'], model_type)
            varid = f"{editor.id['section']}.{editor.id['key']}.{editor.id['subindex']}"
            content = editor_creator(varid, project_id, project_provider)
            components.extend(x for x in iter_components(content) if isinstance(getattr(x, 'id', None), dict))
    return components

@dataclass
class CallbackSpec:
    """The specification of a callback, from `/_dash-dependencies`.

    Attributes:
        output: The output string identifying the callback.
        outputs: (id or pattern, property) of each output, in order.
        inputs: (id or pattern, property) of each input, in order.
        state: (id or pattern, property) of each state, in order.
    """
    output: str
    outputs: list[tuple[str | dict, str]]
    inputs: list[tuple[str | dict, str]]
    state: list[tuple[str | dict, str]]

    @classmethod
    def from_dependency(cls, dep: dict) -> 'CallbackSpec':
        """Read the specification from one entry of `/_dash-dependencies`."""
        output = dep['output']
        if output.startswith('..'):
            parts = output[2:-2].split('...')
        else:
            parts = [output]
        outputs = []
        for x in parts:
            id_, prop = x.rsplit('.', 1)
            outputs.append((_parse_id(id_), prop))
        return cls(
            output = output,
            outputs = outputs,
            inputs = [(_parse_id(x['id']), x['property']) for x in dep['inputs']],
            state = [(_parse_id(x['id']), x['property']) for x in dep['state']],
        )

def get_callback_spec(client, output_type: str, output_property: str) -> CallbackSpec:
    """The specification of the callback which has an output of the components of a type.

    Args:
        client: Flask test client of the app.
        output_type: The type field of the output's id.
        output_property: The property of the output.

    Returns:
        The specification. Raises `LookupError` unless exactly one callback matches.
    """
    response = client.get(DEPENDENCIES_URL)
    assert response.status_code == 200, response.data
    found = []
    for dep in response.get_json():
        spec = CallbackSpec.from_dependency(dep)
        if any(
            isinstance(id_, dict) and id_.get('type') == output_type and prop == output_property
            for id_, prop in spec.outputs
        ):
            found.append(spec)
    if len(found) != 1:
        raise LookupError(f'{len(found)} callbacks output {output_type}.{output_property}')
    return found[0]

def _is_wildcard(pattern: str | dict) -> bool:
    return isinstance(pattern, dict) and any(isinstance(v, list) for v in pattern.values())

def _is_multi_valued(pattern: str | dict) -> bool:
    """Whether a wildcard matches a list of components; with only `MATCH`, it matches one, sent on its own"""
    return isinstance(pattern, dict) and any(v in (['ALL'], ['ALLSMALLER']) for v in pattern.values())

def _matches(pattern: dict, id_: dict, trigger: dict) -> bool:
    """Whether the id matches the pattern, resolving `MATCH` from the trigger"""
    if set(pattern) != set(id_):
        return False
    for k, p in pattern.items():
        match p:
            case ['ALL']:
                continue
            case ['MATCH']:
                if id_[k] != trigger.get(k):
                    return False
            case [other]:
                raise NotImplementedError(f'Wildcard {other} is not supported')
            case _:
                if id_[k] != p:
                    return False
    return True

def _component_value(component: Component, prop: str) -> Any:
    if prop == 'id':
        return component.id
    return getattr(component, prop, None)

@dataclass
class CallbackResponse:
    """The parsed response of a callback.

    Attributes:
        status_code: HTTP status: 200 for an update, 204 when Dash made none (`PreventUpdate`, or all `no_update`).
        updates: Value of each updated property, keyed by (stringified id, property).
    """
    status_code: int
    updates: dict[tuple[str, str], Any] = field(default_factory = dict)

    @property
    def updated(self) -> bool:
        """Whether the callback updated anything."""
        return self.status_code == 200 and bool(self.updates)

    def get(self, id_: str | dict, prop: str, default: Any = NOT_UPDATED) -> Any:
        """The value returned for the property of a component, or `default` if it was not updated."""
        return self.updates.get((stringify_id(id_), prop), default)

    def updated_ids(self, prop: str | None = None) -> list[str | dict]:
        """Ids of the updated components, optionally only those of which the property was updated."""
        return [_parse_id(id_) for id_, p in self.updates if prop is None or p == prop]

def dispatch_callback(
    client,
    spec: CallbackSpec,
    trigger: str | dict,
    value: Any,
    components: Iterable[Component],
    stores: dict[str, Any] | None = None,
    also_triggered: Iterable[tuple[str | dict, Any]] = (),
) -> CallbackResponse:
    """Post a request for a callback, as the browser does when the trigger changes.

    Args:
        client: Flask test client of the app.
        spec: Specification of the callback.
        trigger: Id of the component whose property changed. It must be one of `components`, unless it has a string
            id.
        value: The new value of the property.
        components: The components on the page; those matching each wildcard are sent.
        stores: Values of the dependencies with string ids (e.g. `{'active-project-id': ...}`); others are None.
        also_triggered: (id, value) of other components whose properties changed in the same request.

    Returns:
        The parsed response.
    """
    components = list(components)
    stores = stores or {}
    match_from = trigger if isinstance(trigger, dict) else {}

    if isinstance(trigger, dict) and not any(x.id == trigger for x in components):
        raise ValueError(f'The trigger {trigger} is not among the components of the page')

    def input_property(id_):
        for pattern, prop in spec.inputs:
            if isinstance(pattern, dict) and isinstance(id_, dict):
                if _matches(pattern, id_, match_from):
                    return prop
            elif pattern == id_:
                return prop
        raise ValueError(f'{id_} is not an input of the callback')

    # New values of the changed properties, keyed by (stringified id, property)
    changed = {(stringify_id(trigger), input_property(trigger)): value}
    for id_, v in also_triggered:
        changed[(stringify_id(id_), input_property(id_))] = v

    def dependency(pattern, prop, with_values: bool):
        if _is_wildcard(pattern):
            entries = []
            for c in components:
                if _matches(pattern, c.id, match_from):
                    entry: dict[str, Any] = {'id': c.id, 'property': prop}
                    if with_values:
                        entry['value'] = changed.get((stringify_id(c.id), prop), _component_value(c, prop))
                    entries.append(entry)
            if not _is_multi_valued(pattern):
                if len(entries) != 1:
                    raise ValueError(f'{len(entries)} components match {pattern}, which needs one')
                return entries[0]
            return entries
        entry = {'id': pattern, 'property': prop}
        if with_values:
            entry['value'] = changed.get((stringify_id(pattern), prop), stores.get(pattern))
        return entry

    payload = {
        'output': spec.output,
        'outputs': [dependency(p, prop, False) for p, prop in spec.outputs],
        'inputs': [dependency(p, prop, True) for p, prop in spec.inputs],
        'state': [dependency(p, prop, True) for p, prop in spec.state],
        'changedPropIds': [f'{sid}.{prop}' for sid, prop in changed],
    }
    if len(spec.outputs) == 1:
        payload['outputs'] = payload['outputs'][0]

    response = client.post(UPDATE_URL, json = payload)
    if response.status_code == 204:
        return CallbackResponse(204)
    assert response.status_code == 200, response.data

    updates = {}
    for id_, props in response.get_json()['response'].items():
        for prop, v in props.items():
            updates[(id_, prop)] = v
    return CallbackResponse(200, updates)

def dispatch_input_change(
    client,
    trigger: dict,
    value: Any,
    project_id: str | None,
    model_type: str = 'sprake',
    *,
    components: Iterable[Component],
    also_triggered: Iterable[tuple[dict, Any]] = (),
) -> CallbackResponse:
    """Post a request for `react_to_input_change`, as the browser does when an input of a variable changes.

    Args:
        client: Flask test client of the app.
        trigger: Id of the input which changed; one of `components`.
        value: Its new value (for a button, its `n_clicks`).
        project_id: Id of the active project (the `active-project-id` store), or None.
        model_type: The model type in the `app-state` store.
        components: The components on the page (see `render_input_containers`).
        also_triggered: (id, value) of other inputs which changed in the same request.

    Returns:
        The parsed response.
    """
    spec = get_callback_spec(client, *INPUT_CHANGE_OUTPUT)
    return dispatch_callback(
        client,
        spec,
        trigger,
        value,
        components,
        stores = {
            'active-project-id': project_id,
            'app-state': json.dumps({'model_type': model_type}),
        },
        also_triggered = also_triggered,
    )
