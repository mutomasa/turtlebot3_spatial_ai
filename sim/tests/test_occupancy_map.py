import numpy as np

from room_sim.occupancy_map import load_map_meta, load_occupancy_map, occupied_mask, read_pgm


def test_meta_resolves_image_next_to_yaml(tiny_map):
    meta = load_map_meta(tiny_map)
    assert meta.image == (tiny_map.parent / "m.pgm").resolve()
    assert (meta.resolution, meta.origin_x, meta.origin_y) == (1.0, -1.0, -1.0)


def test_read_pgm_skips_comment_and_keeps_shape(tiny_map):
    pixels = read_pgm(tiny_map.parent / "m.pgm")
    assert pixels.shape == (3, 4)
    assert pixels[1, 3] == 205


def test_unknown_grey_is_not_occupied(tiny_map):
    grid = load_occupancy_map(tiny_map)
    assert grid.occupied[0].all()            # top wall
    assert not grid.occupied[1, 3]           # 205 = unknown
    assert not grid.occupied[2, 1]           # free


def test_negate_inverts_occupancy(tiny_map):
    meta = load_map_meta(tiny_map)
    flipped = meta.__class__(**{**meta.__dict__, "negate": True})
    mask = occupied_mask(np.array([[0, 255]], dtype=np.uint8), flipped)
    assert mask.tolist() == [[False, True]]
