"""CLI: map.yaml -> Gazebo world SDF."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .geometry import is_free, rect_to_box
from .occupancy_map import OccupancyMap, load_occupancy_map
from .rectangles import merge_cells
from .world_sdf import render_world


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("map_yaml", type=Path, help="map_server YAML (e.g. turtlebot3_map.yaml)")
    p.add_argument("-o", "--output", type=Path, required=True, help="output world .sdf")
    p.add_argument("--wall-height", type=float, default=0.5, help="wall height in metres")
    p.add_argument("--spawn-x", type=float, default=0.0, help="spawn point to sanity-check")
    p.add_argument("--spawn-y", type=float, default=0.0)
    return p.parse_args(argv)


def build_world(grid: OccupancyMap, wall_height: float) -> tuple[str, int]:
    if grid.meta.origin_yaw != 0.0:
        raise ValueError("maps with a rotated origin (yaw != 0) are not supported")
    boxes = [rect_to_box(grid, r) for r in merge_cells(grid.occupied)]
    return render_world(boxes, wall_height), len(boxes)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    grid = load_occupancy_map(args.map_yaml)
    if not is_free(grid, args.spawn_x, args.spawn_y):
        print(f"error: spawn ({args.spawn_x}, {args.spawn_y}) is not a free map cell", file=sys.stderr)
        return 1
    sdf, count = build_world(grid, args.wall_height)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(sdf)
    print(f"wrote {args.output} ({count} wall boxes, {grid.cols}x{grid.rows} cells)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
