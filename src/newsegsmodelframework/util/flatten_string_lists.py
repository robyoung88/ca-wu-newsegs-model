"""Helpers for lists of strings and lists of lists of strings.
"""

from collections.abc import Sequence
from typing import List, TypeVar


def flatten_mixed_list(mixed_list: Sequence[List[str] | str]) -> List[str]:
    """Flatten a list of strings and lists of strings into a list of strings.

    Args:
        mixed_list: A list of strings and lists of strings.

    Returns:
        The flat list.
    """
    flat_list=[]
    for item in mixed_list:
        if isinstance(item, str):
            flat_list += [item]
        else:
            flat_list += item
    return flat_list

def len_mixed_list(mixed_list: Sequence[List[str] | str]) -> List[int]:
    """The length of each element of a list of strings and lists of strings; a string counts as 1.

    Args:
        mixed_list: A list of strings and lists of strings.

    Returns:
        The lengths.
    """
    lens=[]
    for item in mixed_list:
        if isinstance(item, str):
            lens += [1]
        else:
            lens += [len(item)]
    return lens

T = TypeVar('T')

def repeat_list_by_index(
    l: Sequence[T], 
    repeats: int | Sequence[int]
) -> List[T]:
    """Repeat each element of a list.

    Raises `AssertionError` if `repeats` is a sequence of a different length.

    Args:
        l: The list.
        repeats: Number of times to repeat each element, or a number for each element.

    Returns:
        The list with each element repeated.
    """
    if not isinstance(repeats, Sequence):
        repeats = [repeats] * len(l)
    assert len(l) == len(repeats), '`repeats` must be a scalar or same length as the list'
    olist = []
    for i in range(len(l)):
        olist.extend([l[i]] * repeats[i])
    return olist
