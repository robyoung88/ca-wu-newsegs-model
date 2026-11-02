"""Configurations module.

TODO: Describe the purpose of the module.
"""
from dataclasses import dataclass
from typing import Callable

from .null_layout import NULL_LAYOUT


@dataclass
class InputCardConfig:
    """Input Card Config.

    TODO: Add a description.
    """
    creation_function: Callable = lambda: NULL_LAYOUT
    block_width: int = 6

@dataclass
class ResultCardConfig:
    """Result Card Config.

    TODO: Add a description.
    """
    creation_function: Callable = lambda: NULL_LAYOUT
    block_width: int = 6
    