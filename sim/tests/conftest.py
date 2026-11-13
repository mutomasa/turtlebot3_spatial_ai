from pathlib import Path

import numpy as np
import pytest


def write_pgm(path: Path, pixels: np.ndarray, comment: bool = False) -> None:
    h, w = pixels.shape
    header = b"P5\n" + (b"# made by test\n" if comment else b"") + f"{w} {h}\n255\n".encode()
    path.write_bytes(header + pixels.astype(np.uint8).tobytes())


@pytest.fixture
def tiny_map(tmp_path: Path) -> Path:
    """4 cols x 3 rows, 1 m cells, origin (-1, -1). Black (0) = wall, white (254) = free."""
    pixels = np.array([
        [0,   0,   0,   0],
        [0, 254, 254, 205],
        [0, 254, 254, 254],
    ])
    write_pgm(tmp_path / "m.pgm", pixels, comment=True)
    (tmp_path / "m.yaml").write_text(
        "image: m.pgm\nmode: trinary\nresolution: 1.0\norigin: [-1.0, -1.0, 0]\n"
        "negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n"
    )
    return tmp_path / "m.yaml"
