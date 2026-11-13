import xml.etree.ElementTree as ET

import pytest

from room_sim.cli import build_world, main
from room_sim.geometry import cell_center, is_free, rect_to_box
from room_sim.occupancy_map import load_occupancy_map
from room_sim.rectangles import CellRect


def test_top_left_cell_centre_is_at_max_y(tiny_map):
    grid = load_occupancy_map(tiny_map)
    # origin (-1,-1) is the bottom-left corner; 3 rows of 1 m -> top row centre y = 1.5
    assert cell_center(grid, 0, 0) == (-0.5, 1.5)
    assert cell_center(grid, 2, 3) == (2.5, -0.5)


def test_rect_to_box_spans_cells(tiny_map):
    grid = load_occupancy_map(tiny_map)
    box = rect_to_box(grid, CellRect(row=0, col=0, height=1, width=4))
    assert (box.x, box.y, box.size_x, box.size_y) == (1.0, 1.5, 4.0, 1.0)


def test_is_free(tiny_map):
    grid = load_occupancy_map(tiny_map)
    assert is_free(grid, 0.5, 0.5)          # free cell (row 1, col 1)
    assert not is_free(grid, 0.5, 1.5)      # top wall
    assert not is_free(grid, 10.0, 0.0)     # outside the map


def test_world_is_valid_xml_with_walls(tiny_map):
    sdf, count = build_world(load_occupancy_map(tiny_map), wall_height=0.4)
    root = ET.fromstring(sdf)
    walls = root.find("./world/model[@name='scanned_room']/link")
    assert count == 2  # top row + left column below it
    assert len(walls.findall("collision")) == count
    assert walls.find("collision/geometry/box/size").text.split()[2] == "0.4000"


def test_cli_rejects_spawn_inside_wall(tiny_map, tmp_path):
    out = tmp_path / "w.sdf"
    assert main([str(tiny_map), "-o", str(out), "--spawn-x", "0.5", "--spawn-y", "1.5"]) == 1
    assert not out.exists()


def test_cli_writes_world(tiny_map, tmp_path):
    out = tmp_path / "w.sdf"
    assert main([str(tiny_map), "-o", str(out), "--spawn-x", "0.5", "--spawn-y", "0.5"]) == 0
    assert out.read_text().startswith("<?xml")


def test_rotated_origin_is_rejected(tiny_map):
    tiny_map.write_text(tiny_map.read_text().replace("[-1.0, -1.0, 0]", "[-1.0, -1.0, 0.3]"))
    with pytest.raises(ValueError):
        build_world(load_occupancy_map(tiny_map), 0.5)
