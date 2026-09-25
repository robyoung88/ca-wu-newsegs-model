from dataclasses import dataclass
from typing import Callable

from .null_layout import NULL_LAYOUT


@dataclass
class InputCardConfig:
    creation_function: Callable = lambda: NULL_LAYOUT
    block_width: int = 6

@dataclass
class ResultCardConfig:
    creation_function: Callable = lambda: NULL_LAYOUT
    block_width: int = 6
    