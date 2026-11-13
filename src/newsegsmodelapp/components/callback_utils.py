"""Helpers for Dash callbacks, such as finding the value of the component that triggered a callback.

Several inputs of a callback can fire in the same call. Dash then lists them all in `ctx.triggered`, but
`ctx.triggered_id` and `get_triggered_value` give only the first. A callback with several inputs should consider every
trigger, with `get_triggers`, `get_clicked_trigger` or `ids_to_update`.
"""
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import json
from typing import Any

import dash
from dash import ctx, no_update

# -----------------------------------------------
# Triggers
# -----------------------------------------------

@dataclass(frozen = True)
class Trigger:
    """An input of a callback which fired: an entry of `ctx.triggered`, with its id parsed.

    Attributes:
        id: The id of the component: a string, or the dictionary of a pattern-matching id.
        property: The property which changed.
        value: Its new value.
    """
    id: str | dict[str, Any]
    property: str
    value: Any

    @property
    def type(self) -> str | None:
        """The type of a pattern-matching id, or None for a string id."""
        return self.id.get('type') if isinstance(self.id, dict) else None

    def is_pattern(self) -> bool:
        """Whether the id is a pattern-matching (dictionary) id."""
        return isinstance(self.id, dict)

def parse_prop_id(prop_id: str) -> tuple[str | dict[str, Any] | None, str]:
    """The id and property of a `prop_id` of `ctx.triggered`.

    Args:
        prop_id: `<id>.<property>`, where the id is JSON if a pattern-matching id; `.` on the initial call.

    Returns:
        The id (a dictionary for a pattern-matching id; None on the initial call) and the property.
    """
    id_text, _, prop = prop_id.rpartition('.')
    if not id_text:
        return None, prop
    if id_text.startswith('{'):
        try:
            return json.loads(id_text), prop
        except ValueError:
            pass
    return id_text, prop

def get_triggers(triggered: Iterable[dict] | None = None) -> list[Trigger]:
    """Every input which triggered the callback, in the order of `ctx.triggered`.

    Args:
        triggered: The entries of `ctx.triggered`; by default those of the current callback.

    Returns:
        The triggers; empty on the initial call, when Dash gives a single entry with an empty id.
    """
    if triggered is None:
        triggered = ctx.triggered
    triggers = []
    for entry in triggered:
        id_, prop = parse_prop_id(entry.get('prop_id', '.'))
        if id_ is None:
            continue
        triggers.append(Trigger(id_, prop, entry.get('value')))
    return triggers

def has_trigger(triggers: Iterable[Trigger], id_: str) -> bool:
    """Whether the component with a string id is among the triggers."""
    return any(x.id == id_ for x in triggers)

def get_clicked_trigger(triggers: Sequence[Trigger] | None = None) -> Trigger | None:
    """The one trigger with a value, as of a button clicked, for a callback with several buttons as inputs.

    Buttons fire together when they are drawn, with no clicks, so the triggers without a value are ignored. Two
    buttons can't be clicked at once, so if several triggers have a value, which was clicked is unknown.

    Args:
        triggers: The triggers; by default those of the current callback.

    Returns:
        The trigger, or None if none, or several, have a value.
    """
    if triggers is None:
        triggers = get_triggers()
    clicked = [x for x in triggers if x.value]
    return clicked[0] if len(clicked) == 1 else None

def ids_to_update(
    triggers: Iterable[Trigger],
    target_ids: Sequence[dict[str, Any]],
    target_type: str,
    target_purpose: str,
    update_all_types: Iterable[str] = (),
    ignored_keys: Iterable[str] = ('subindex', 'supersection'),
) -> list[dict[str, Any]]:
    """The ids of the targets of a callback (e.g. containers) to redraw for its triggers.

    Every trigger is considered. A trigger with a string id (e.g. an interval, or a store such as the active
    project), with a type in `update_all_types`, or with no `section`, redraws every target; so does the initial call
    (no triggers). Otherwise the targets redrawn are those whose id agrees with the trigger's, apart from its type,
    purpose and `ignored_keys`.

    Args:
        triggers: The triggers (see `get_triggers`).
        target_ids: The ids of the targets.
        target_type: Type of the ids of the targets, e.g. 'result-table'.
        target_purpose: Purpose of the ids of the targets, e.g. 'container'.
        update_all_types: Types of the triggers which redraw every target.
        ignored_keys: Keys of the triggers' ids not compared with the targets'.

    Returns:
        The ids to redraw, each once, in the order of `target_ids`.
    """
    triggers = list(triggers)
    update_all_types = set(update_all_types)
    ignored_keys = set(ignored_keys)
    if not triggers:
        return list(target_ids)
    matches = []
    for trig in triggers:
        if not trig.is_pattern() or trig.type in update_all_types or 'section' not in trig.id:
            return list(target_ids)
        match = {k: v for k, v in trig.id.items() if k not in ignored_keys} # pyright: ignore[reportAttributeAccessIssue]
        match.update(type = target_type, purpose = target_purpose)
        matches.append(match)
    return [x for x in target_ids if any(intersection_values_match(m, x) for m in matches)]

def get_options(
    option_ids: list[dict[str, str]],
    option_values: list[Any],
    page: str,
    keys: list[str]
) -> dict[str, Any]:
    """
    Get matched values from paired lists of id dictionaries and values.

    Matches on keys 'page' (always) and 'key' (as member of key list).

    Args:
        option_ids (list[dict[str, str]]): List of dictionaries containing 'page' and 'key' keys with string values.
        option_values (list[Any]): List of equal length to option_ids containing the matched option values.
        page (str): Value required for 'page' in `option_ids`.
        keys (list[str]): Strings to be found in 'key' key within `option_ids`. Form the keys of the returned dict.

    Returns:
        dict[str, Any]: key:value pairs for any of the keys found in the `option_ids` list on the correct page.
    """
    odict = {}
    for id, val in zip(option_ids, option_values):
        if id.get('page') == page and id.get('key') in keys:
            odict[id['key']] = val
    return odict

def get_options_nopage(
    option_ids: list[dict[str, str]],
    option_values: list[Any],
    keys: list[str]
) -> dict[str, Any]:
    """
    Get matched values from paired lists of id dictionaries and values.

    Matches on 'key' (as member of key list).

    Args:
        option_ids (list[dict[str, str]]): List of dictionaries containing 'page' and 'key' keys with string values.
        option_values (list[Any]): List of equal length to option_ids containing the matched option values.
        keys (list[str]): Strings to be found in 'key' key within `option_ids`. Form the keys of the returned dict.

    Returns:
        dict[str, Any]: key:value pairs for any of the keys found in the `option_ids` list on the correct page.
    """
    odict = {}
    for id, val in zip(option_ids, option_values):
        if id.get('key') in keys:
            odict[id['key']] = val
    return odict

# REVIEW (unreferenced): no references to `get_variable_keyed_data` found in src/, scripts/ or data/.
def get_variable_keyed_data(
    section: str,
    key: str,
    subindex: int,
    ids: list[dict[str, str|int]],
    values: list[Any]
) -> Any:
    """
    Get value from paired list of id dictionaries and values where section, key and subindex match

    Args:
        section (str): Interface section
        key (str): Interface key
        subindex (int): Interface subindex
        ids (list[dict[str, str|int]]): List of dictionaries containing 'section', 'key' and 'subindex' keys
        values (list[Any]): List of equal length to `ids` containing the matched option values.

    Returns:
        Any: Value at index of first match of section, key, subindex in `ids` or None
    """
    for id, val in zip(ids, values):
        if (
            id.get('section') == section
            and id.get('key') == key
            and id.get('subindex') == subindex
        ):
            return val
    return None

def get_triggered_value() -> Any:
    """
    In the context of a Dash callback, return the value of the prop that triggered the callback.

    Only the first trigger is considered: where several inputs may fire together, use `get_triggers` or
    `get_clicked_trigger`.

    Returns `None` if triggered on creation.
    Returns:
        Any: The value of the prop that triggered the callback.
    """
    trig_id = ctx.triggered_id
    if trig_id is None:
        return None
    isdict = isinstance(trig_id, dict)

    val = None
    for prop in ctx.triggered:
        pid = prop['prop_id'].rsplit('.',1)[0]
        if isdict:
            try:
                pid = json.loads(pid)
            except json.decoder.JSONDecodeError:
                pass
        if pid == trig_id:
            val = prop['value']
            break
    return val

# REVIEW (unreferenced): no references to `update_return_list` found in src/, scripts/ or data/.
def update_return_list(
    update_id: dict[str, Any],
    update_value: Any,
    ids: list[dict[str, Any]],
    values: list[Any]
) -> bool:
    """
    Search `ids` list of dicts for a match with `update_id`, and set matching indices in `values` with `update_value`

    Args:
        update_id (dict[str, Any]): Search dictionary value (all keys and values must match)
        update_value (Any): Value to apply to matched indices in `values` list
        ids (list[dict[str, Any]]): List of id dictionaries to search
        values (list[Any]): List of values to update

    Returns:
        bool: `True` if at least one value has been updated, `False` otherwise
    """
    updated = False
    for idx, id in enumerate(ids):
        if id == update_id:
            values[idx] = update_value
            updated = True
    return updated

def _create_noupdate_return(out: Any):
    if isinstance(out, list):
        # Assume list of id property pairs
        return [no_update]*len(out)
    elif isinstance(out, dash._utils.AttributeDict):
            return {k: _create_noupdate_return(v) for k, v in out.items()}
    elif isinstance(out, dict):
        # A single id property pair
        return no_update
    else:
        raise TypeError(f'Unhandled output specification type: {type(out)}')

def create_noupdate_return() -> Any:
    """Within a callback, use the context to create the noupdate return"""

    if ctx.using_outputs_grouping:
        return _create_noupdate_return(ctx.outputs_grouping)

    return _create_noupdate_return(ctx.outputs_list)

def intersection_values_match(d1, d2):
    """Whether two dictionaries agree on the keys that they share.

    Args:
        d1: First dictionary.
        d2: Second dictionary.

    Returns:
        True if the values of every shared key are equal.
    """
    return all(d1[k] == d2[k] for k in (d1.keys() & d2.keys()))

def _find_output_locations(
    id: str | dict,
    property: str,
    search_object
) -> list:
    return_locs = []
    if isinstance(search_object, dash._utils.AttributeDict):
        for k, v in search_object.items():
            new_locs = _find_output_locations(id, property, v)
            if new_locs:
                return_locs.append([k, new_locs])
    elif isinstance(search_object, dict):
        if not(str(search_object['property']).startswith(property)):
            return []
        obj_id = search_object['id']
        if type(obj_id) != type(id):
            return []
        if isinstance(id, str):
            if obj_id == id:
                return_locs.append(True)
        elif isinstance(id, dict):
            if intersection_values_match(obj_id, id):
                return_locs.append(True)
    elif isinstance(search_object, list):
        for idx, v in enumerate(search_object):
            new_locs = _find_output_locations(id, property, v)
            if new_locs:
                return_locs.append([idx, new_locs])

    return return_locs

def _update_these_elements(element_index, update_value, return_value):
    for keyval in element_index:
        key = keyval[0]
        val = keyval[1]
        if isinstance(val[0], bool):
            return_value[key] = update_value
        else:
            _update_these_elements(
                val, update_value, return_value[key]
            )

def update_property_by_id(
    id: str|dict,
    property: str,
    update_value: Any,
    out: Any | None
) -> Any:
    """Update an output by providing an exact id and property
    
    Provide `out` to modify an existing return list or dictionary
"""
    if not out:
        out = create_noupdate_return()

    if ctx.using_outputs_grouping:
        locations_to_update = _find_output_locations(id, property, ctx.outputs_grouping)
    else:
        locations_to_update = _find_output_locations(id, property, ctx.outputs_list)

    if not locations_to_update:
        return out

    _update_these_elements(locations_to_update, update_value, out)
        
    return out
