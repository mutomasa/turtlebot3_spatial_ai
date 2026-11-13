"""Convert grid rectangles into wall boxes in the map frame (metres)."""
from __future__ import annotations

from dataclasses import dataclass

from .occupancy_map import OccupancyMap
from .rectangles import CellRect


@dataclass(frozen=True)
class WallBox:
    x: float       # centre, map frame
    y: float
    size_x: float
    size_y: float


def cell_center(grid: OccupancyMap, row: int, col: int) -> tuple[float, float]:
    """Centre of a cell in the map frame; image row 0 is the top (max y)."""
    res = grid.meta.resolution
    x = grid.meta.origin_x + (col + 0.5) * res
    y = grid.meta.origin_y + (grid.rows - row - 0.5) * res
    return x, y


def rect_to_box(grid: OccupancyMap, rect: CellRect) -> WallBox:
    res = grid.meta.resolution
    x0, y_top = cell_center(grid, rect.row, rect.col)
    return WallBox(
        x=x0 + (rect.width - 1) * res / 2.0,
        y=y_top - (rect.height - 1) * res / 2.0,
        size_x=rect.width * res,
        size_y=rect.height * res,
    )


def is_free(grid: OccupancyMap, x: float, y: float) -> bool:
    """True when the map-frame point lies inside the grid on an unoccupied cell."""
    res = grid.meta.resolution
    col = int((x - grid.meta.origin_x) // res)
    row = grid.rows - 1 - int((y - grid.meta.origin_y) // res)
    inside = 0 <= row < grid.rows and 0 <= col < grid.cols
    return inside and not bool(grid.occupied[row, col])
