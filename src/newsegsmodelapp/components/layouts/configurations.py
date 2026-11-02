"""Configuration of the cards of inputs and results of a page.
"""
from dataclasses import dataclass
from typing import Callable

from .null_layout import NULL_LAYOUT


@dataclass
class InputCardConfig:
    """Configuration of a card of inputs on a page.

    Attributes:
        creation_function: Function which creates the card.
        block_width: Width of the card, in columns of the page grid.
    """
    creation_function: Callable = lambda: NULL_LAYOUT
    block_width: int = 6

@dataclass
class ResultCardConfig:
    """Configuration of a card of results on a page.

    Attributes:
        creation_function: Function which creates the card.
        block_width: Width of the card, in columns of the page grid.
    """
    creation_function: Callable = lambda: NULL_LAYOUT
    block_width: int = 6
    