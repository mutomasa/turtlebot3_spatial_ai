"""シナリオテストの共通部品。

実行方法（sim パッケージの環境を使う）:

    cd sim && uv run pytest ../tests
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_MAP_YAML = REPO_ROOT / "sim" / "maps" / "turtlebot3_map.yaml"

FREE, UNKNOWN, WALL = 254, 205, 0


@dataclass(frozen=True)
class SdfBox:
    name: str
    x: float
    y: float
    z: float
    size_x: float
    size_y: float
    size_z: float


def parse_world(sdf_path: Path) -> tuple[list[SdfBox], list[SdfBox]]:
    """ワールドSDFから、壁の collision と visual の箱を取り出す。"""
    root = ET.parse(sdf_path).getroot()
    link = root.find("./world/model[@name='scanned_room']/link[@name='walls']")
    assert link is not None, "scanned_room モデルの walls リンクがない"

    def boxes(tag: str) -> list[SdfBox]:
        out = []
        for el in link.findall(tag):
            x, y, z, *_ = map(float, el.findtext("pose").split())
            sx, sy, sz = map(float, el.findtext("geometry/box/size").split())
            out.append(SdfBox(el.get("name"), x, y, z, sx, sy, sz))
        return out

    return boxes("collision"), boxes("visual")


def write_map(directory: Path, pixels: np.ndarray, resolution: float,
              origin: tuple[float, float, float], name: str = "room") -> Path:
    """map_server 形式（PGM + YAML）の地図を書き出し、YAML のパスを返す。"""
    h, w = pixels.shape
    (directory / f"{name}.pgm").write_bytes(
        f"P5\n{w} {h}\n255\n".encode() + pixels.astype(np.uint8).tobytes())
    (directory / f"{name}.yaml").write_text(
        f"image: {name}.pgm\nmode: trinary\nresolution: {resolution}\n"
        f"origin: [{origin[0]}, {origin[1]}, {origin[2]}]\n"
        "negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n")
    return directory / f"{name}.yaml"


@pytest.fixture
def real_map_yaml() -> Path:
    if not REAL_MAP_YAML.exists():
        pytest.skip(f"実機の地図がない: {REAL_MAP_YAML}")
    return REAL_MAP_YAML


@pytest.fixture
def room_with_table(tmp_path: Path) -> Path:
    """4m x 3m の部屋（0.1m セル）。外周は壁、中央に 0.6m x 0.4m の机、右上の角は未知領域。

    原点は (-2.0, -1.5)。部屋の中心が map 座標の (0, 0) になる。
    机は x: -0.3〜0.3、y: -0.2〜0.2 を占める。
    """
    rows, cols = 30, 40
    px = np.full((rows, cols), FREE)
    px[0, :] = px[-1, :] = WALL
    px[:, 0] = px[:, -1] = WALL
    px[13:17, 17:23] = WALL          # 机
    px[1:4, 35:39] = UNKNOWN         # まだ観測していない領域
    return write_map(tmp_path, px, resolution=0.1, origin=(-2.0, -1.5, 0.0))
