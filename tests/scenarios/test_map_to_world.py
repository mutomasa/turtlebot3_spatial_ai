"""シナリオテスト：実機で作った地図から Gazebo のワールドを作る。

ユーザーの使い方（sim/README.md）をそのままなぞる。

    room-sim-world maps/turtlebot3_map.yaml -o worlds/scanned_room.sdf --wall-height 0.5

CLI を入口にして、出力された SDF を読み戻し、地図と一致するかを確かめる。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from conftest import parse_world, write_map

from room_sim.cli import main
from room_sim.occupancy_map import load_occupancy_map

EPS = 1e-3


def rasterize(boxes, grid) -> np.ndarray:
    """SDF の箱を地図のセルに塗り戻す。同じセルを2回塗ったら重なりとして数える。"""
    res = grid.meta.resolution
    count = np.zeros(grid.occupied.shape, dtype=int)
    for b in boxes:
        col0 = round((b.x - b.size_x / 2 - grid.meta.origin_x) / res)
        col1 = round((b.x + b.size_x / 2 - grid.meta.origin_x) / res)
        y0 = round((b.y - b.size_y / 2 - grid.meta.origin_y) / res)
        y1 = round((b.y + b.size_y / 2 - grid.meta.origin_y) / res)
        row0, row1 = grid.rows - y1, grid.rows - y0  # 画像の行は上が0
        count[row0:row1, col0:col1] += 1
    return count


def point_in_box(x: float, y: float, b) -> bool:
    return abs(x - b.x) < b.size_x / 2 and abs(y - b.y) < b.size_y / 2


# ---------------------------------------------------------------------------
# シナリオ1：実機の地図からワールドを作り、シミュレーターに渡せる形になっている
# ---------------------------------------------------------------------------

def test_real_map_becomes_world_that_matches_the_map(real_map_yaml, tmp_path, capsys):
    out = tmp_path / "worlds" / "scanned_room.sdf"

    code = main([str(real_map_yaml), "-o", str(out), "--wall-height", "0.5"])

    assert code == 0
    assert out.exists(), "出力先のディレクトリが自動で作られていない"
    assert "wall boxes" in capsys.readouterr().out

    collisions, visuals = parse_world(out)
    grid = load_occupancy_map(real_map_yaml)

    # 衝突判定と見た目が1対1で、同じ位置・大きさ
    assert len(collisions) == len(visuals) > 0
    for c, v in zip(collisions, visuals):
        assert (c.x, c.y, c.size_x, c.size_y) == (v.x, v.y, v.size_x, v.size_y)

    # 壁の高さと、床に接地していること
    assert all(abs(b.size_z - 0.5) < EPS and abs(b.z - 0.25) < EPS for b in collisions)

    # 占有セルが過不足なく、重なりなく壁になっている
    count = rasterize(collisions, grid)
    assert np.array_equal(count > 0, grid.occupied)
    assert count.max() == 1

    # 長方形にまとめた結果、セル数より箱の数が少ない
    assert len(collisions) < int(grid.occupied.sum())


def test_default_spawn_point_is_not_inside_a_wall(real_map_yaml, tmp_path):
    """既定の出現位置 (0, 0) にロボットを置いても、壁にめり込まない。"""
    out = tmp_path / "w.sdf"
    assert main([str(real_map_yaml), "-o", str(out)]) == 0

    collisions, _ = parse_world(out)
    assert not any(point_in_box(0.0, 0.0, b) for b in collisions)


def test_world_is_rebuilt_identically_every_launch(real_map_yaml, tmp_path):
    """起動のたびにワールドを作り直すので、同じ地図からは同じワールドができる。"""
    a, b = tmp_path / "a.sdf", tmp_path / "b.sdf"
    assert main([str(real_map_yaml), "-o", str(a)]) == 0
    assert main([str(real_map_yaml), "-o", str(b)]) == 0
    assert a.read_bytes() == b.read_bytes()


# ---------------------------------------------------------------------------
# シナリオ2：机のある部屋。ロボットが通れる場所と通れない場所が地図どおりになる
# ---------------------------------------------------------------------------

def test_room_walls_and_table_are_placed_in_map_coordinates(room_with_table, tmp_path):
    out = tmp_path / "room.sdf"
    assert main([str(room_with_table), "-o", str(out), "--spawn-x", "1.0", "--spawn-y", "0.5"]) == 0

    collisions, _ = parse_world(out)
    blocked = lambda x, y: any(point_in_box(x, y, b) for b in collisions)  # noqa: E731

    # 机の上と外周の壁は通れない
    assert blocked(0.0, 0.0)
    assert blocked(0.25, -0.15)
    assert blocked(-1.95, 0.0) and blocked(1.95, 0.0)
    assert blocked(0.0, -1.45) and blocked(0.0, 1.45)

    # 机のまわりの通路と出現位置は通れる
    assert not blocked(1.0, 0.5)
    assert not blocked(0.0, 0.35)
    assert not blocked(-0.45, 0.0)

    # 未知領域は壁にしない（まだ見ていない場所を障害物と決めつけない）
    assert not blocked(1.65, 1.2)

    # 壁はすべて部屋の中に収まる
    for b in collisions:
        assert -2.0 - EPS <= b.x - b.size_x / 2 and b.x + b.size_x / 2 <= 2.0 + EPS
        assert -1.5 - EPS <= b.y - b.size_y / 2 and b.y + b.size_y / 2 <= 1.5 + EPS


# ---------------------------------------------------------------------------
# シナリオ3：使い方を間違えたとき、壊れたワールドを作らずに止まる
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("spawn", [(0.0, 0.0), (-1.95, 0.0), (5.0, 5.0)],
                         ids=["on_table", "in_wall", "outside_map"])
def test_bad_spawn_point_is_rejected_without_writing_world(room_with_table, tmp_path, capsys, spawn):
    out = tmp_path / "room.sdf"

    code = main([str(room_with_table), "-o", str(out),
                 "--spawn-x", str(spawn[0]), "--spawn-y", str(spawn[1])])

    assert code == 1
    assert not out.exists()
    assert "not a free map cell" in capsys.readouterr().err


def test_rotated_map_origin_is_rejected(tmp_path):
    """原点が回転した地図には対応していないので、黙ってずれたワールドを作らない。"""
    px = np.full((5, 5), 254)
    px[0, :] = 0
    yaml_path = write_map(tmp_path, px, resolution=0.1, origin=(-0.25, -0.25, 0.5))

    with pytest.raises(ValueError, match="rotated origin"):
        main([str(yaml_path), "-o", str(tmp_path / "w.sdf")])
    assert not (tmp_path / "w.sdf").exists()


def test_missing_output_option_exits_with_usage_error(real_map_yaml):
    with pytest.raises(SystemExit) as exc:
        main([str(real_map_yaml)])
    assert exc.value.code == 2


def test_empty_room_produces_world_with_no_walls(tmp_path):
    """まだ何も観測していない地図でも、床だけのワールドを作れる。"""
    yaml_path = write_map(tmp_path, np.full((10, 10), 254), resolution=0.1,
                          origin=(-0.5, -0.5, 0.0))
    out = tmp_path / "empty.sdf"

    assert main([str(yaml_path), "-o", str(out)]) == 0
    collisions, visuals = parse_world(Path(out))
    assert collisions == [] and visuals == []
