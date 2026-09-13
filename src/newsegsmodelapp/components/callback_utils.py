import json
from typing import Any

from dash import ctx

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