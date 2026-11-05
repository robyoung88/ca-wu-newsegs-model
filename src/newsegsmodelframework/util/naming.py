"""Default names of the things users name: copies of projects and configurations."""

import re
from collections.abc import Iterable

_COPY_SUFFIX = re.compile(r'^(?P<base>.*?)\s*\(copy(?: (?P<n>\d+))?\)$')

def copy_name(name: str, existing: Iterable[str] = ()) -> str:
    """The name of a copy: the name with a numbered copy suffix, unique among the existing names.

    The suffix of a copy of a copy replaces the source's, so suffixes don't stack: copies of "Baseline" are
    "Baseline (copy)", "Baseline (copy 2)", "Baseline (copy 3)"..., and so are copies of those copies.

    Args:
        name: The name of the source.
        existing: The names the copy must not take, such as those of the other configurations of the project.

    Returns:
        The name of the copy.
    """
    match = _COPY_SUFFIX.match(name)
    base = match.group('base') if match else name
    taken = set(existing)
    candidate = f'{base} (copy)'
    n = 1
    while candidate in taken:
        n += 1
        candidate = f'{base} (copy {n})'
    return candidate

def unique_name(name: str, existing: Iterable[str] = ()) -> str:
    """A name, or the name of a copy of it if the name is taken.

    Args:
        name: The name.
        existing: The names already taken.

    Returns:
        `name` if it isn't in `existing`, otherwise `copy_name(name, existing)`.
    """
    existing = set(existing)
    return name if name not in existing else copy_name(name, existing)
