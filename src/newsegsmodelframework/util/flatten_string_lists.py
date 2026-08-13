"""
Tools to flatten mixed lists of strings and lists of strings.
"""

from collections.abc import Sequence
from typing import List, TypeVar


def flatten_mixed_list(mixed_list: Sequence[List[str] | str]) -> List[str]:
    flat_list=[]
    for item in mixed_list:
        if isinstance(item, str):
            flat_list += [item]
        else:
            flat_list += item
    return flat_list

def len_mixed_list(mixed_list: Sequence[List[str] | str]) -> List[int]:
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
    if not isinstance(repeats, Sequence):
        repeats = [repeats] * len(l)
    assert len(l) == len(repeats), '`repeats` must be a scalar or same length as the list'
    olist = []
    for i in range(len(l)):
        olist.extend([l[i]] * repeats[i])
    return olist
