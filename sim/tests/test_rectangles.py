import numpy as np

from room_sim.rectangles import CellRect, merge_cells


def _coverage(rects, shape):
    cover = np.zeros(shape, dtype=int)
    for r in rects:
        cover[r.row:r.row + r.height, r.col:r.col + r.width] += 1
    return cover


def test_full_block_becomes_one_rect():
    assert merge_cells(np.ones((3, 5), dtype=bool)) == [CellRect(0, 0, 3, 5)]


def test_empty_mask_has_no_rects():
    assert merge_cells(np.zeros((4, 4), dtype=bool)) == []


def test_l_shape_covers_each_cell_exactly_once():
    mask = np.array([
        [1, 1, 1],
        [1, 0, 0],
        [1, 0, 0],
    ], dtype=bool)
    rects = merge_cells(mask)
    assert (_coverage(rects, mask.shape) == mask.astype(int)).all()
    assert len(rects) == 2


def test_random_masks_are_exactly_covered():
    rng = np.random.default_rng(0)
    for _ in range(20):
        mask = rng.random((15, 12)) > 0.6
        cover = _coverage(merge_cells(mask), mask.shape)
        assert (cover == mask.astype(int)).all()
