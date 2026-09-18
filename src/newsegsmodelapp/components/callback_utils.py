import copy
import json
from typing import Any

import dash
from dash import ctx, no_update
from dash.exceptions import PreventUpdate

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
    return all(d1[k] == d2[k] for k in (d1.keys() & d2.keys()))

def _find_output_locations(
    id: str | dict,
    property: str,
    search_object
):
    return_locs = []
    if isinstance(search_object, dash._utils.AttributeDict):
        for k, v in search_object.items():
            new_locs = _find_output_locations(id, property, v)
            if new_locs:
                return_locs.append([k, new_locs])
    elif isinstance(search_object, dict):
        if search_object['property'] != property:
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

def update_return_by_id(
    id: str|dict,
    property: str,
    update_value: Any,
    return_value: Any | None
) -> Any:
    if not return_value:
        return_value = create_noupdate_return()

    if ctx.using_outputs_grouping:
        locations_to_update = _find_output_locations(id, property, ctx.outputs_grouping)
    else:
        locations_to_update = _find_output_locations(id, property, ctx.outputs_list)

    if not locations_to_update:
        return return_value

    _update_these_elements(locations_to_update, update_value, return_value)
        
    return return_value
