"""Load a ROS map_server map (YAML metadata + PGM image) into an occupancy mask."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml


@dataclass(frozen=True)
class MapMeta:
    image: Path
    resolution: float
    origin_x: float
    origin_y: float
    origin_yaw: float
    occupied_thresh: float
    negate: bool


@dataclass(frozen=True)
class OccupancyMap:
    meta: MapMeta
    occupied: np.ndarray  # bool, shape (rows, cols); row 0 is the TOP of the image

    @property
    def rows(self) -> int:
        return self.occupied.shape[0]

    @property
    def cols(self) -> int:
        return self.occupied.shape[1]


def load_map_meta(yaml_path: Path) -> MapMeta:
    data = yaml.safe_load(Path(yaml_path).read_text())
    origin = data["origin"]
    return MapMeta(
        image=(Path(yaml_path).parent / data["image"]).resolve(),
        resolution=float(data["resolution"]),
        origin_x=float(origin[0]),
        origin_y=float(origin[1]),
        origin_yaw=float(origin[2]),
        occupied_thresh=float(data.get("occupied_thresh", 0.65)),
        negate=bool(data.get("negate", 0)),
    )


def _read_header_tokens(raw: bytes, count: int) -> tuple[list[bytes], int]:
    """Read `count` whitespace-separated header tokens, skipping # comments."""
    tokens: list[bytes] = []
    pos = 0
    while len(tokens) < count:
        while raw[pos:pos + 1].isspace():
            pos += 1
        if raw[pos:pos + 1] == b"#":
            pos = raw.index(b"\n", pos) + 1
            continue
        start = pos
        while not raw[pos:pos + 1].isspace():
            pos += 1
        tokens.append(raw[start:pos])
    return tokens, pos + 1  # exactly one whitespace byte follows maxval


def read_pgm(path: Path) -> np.ndarray:
    """Read a binary (P5) 8-bit PGM image as a uint8 array."""
    raw = Path(path).read_bytes()
    (magic, width, height, maxval), offset = _read_header_tokens(raw, 4)
    if magic != b"P5" or int(maxval) > 255:
        raise ValueError(f"{path}: only 8-bit binary PGM (P5) is supported")
    w, h = int(width), int(height)
    pixels = np.frombuffer(raw, dtype=np.uint8, count=w * h, offset=offset)
    return pixels.reshape(h, w)


def occupied_mask(pixels: np.ndarray, meta: MapMeta) -> np.ndarray:
    """Apply map_server's rule: occupancy p = (255 - v) / 255 (inverted if negate)."""
    p = pixels.astype(np.float64) / 255.0
    if not meta.negate:
        p = 1.0 - p
    return p > meta.occupied_thresh


def load_occupancy_map(yaml_path: Path) -> OccupancyMap:
    meta = load_map_meta(yaml_path)
    return OccupancyMap(meta=meta, occupied=occupied_mask(read_pgm(meta.image), meta))
