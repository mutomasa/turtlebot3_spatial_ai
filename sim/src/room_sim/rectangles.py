"""Cover the occupied cells of a grid with a small number of axis-aligned rectangles."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CellRect:
    row: int   # top row (image coordinates)
    col: int   # left column
    height: int
    width: int


def _grow_right(mask: np.ndarray, used: np.ndarray, row: int, col: int) -> int:
    width = 1
    while col + width < mask.shape[1] and mask[row, col + width] and not used[row, col + width]:
        width += 1
    return width


def _grow_down(mask: np.ndarray, used: np.ndarray, row: int, col: int, width: int) -> int:
    height = 1
    while row + height < mask.shape[0]:
        span = slice(col, col + width)
        if not (mask[row + height, span].all() and not used[row + height, span].any()):
            break
        height += 1
    return height


def merge_cells(mask: np.ndarray) -> list[CellRect]:
    """Greedy row-major merge; every occupied cell ends up in exactly one rectangle."""
    used = np.zeros_like(mask, dtype=bool)
    rects: list[CellRect] = []
    for row, col in zip(*np.nonzero(mask)):
        if used[row, col]:
            continue
        width = _grow_right(mask, used, row, col)
        height = _grow_down(mask, used, row, col, width)
        used[row:row + height, col:col + width] = True
        rects.append(CellRect(int(row), int(col), height, width))
    return rects
