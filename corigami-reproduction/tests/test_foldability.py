import math

import pytest

from corigami.cp import BORDER, MOUNTAIN, VALLEY, CreasePattern
from corigami.foldability import (
    check_pattern,
    crimp_foldable,
    kawasaki,
    maekawa,
)


def test_kawasaki_waterbomb():
    # waterbomb vertex: 8 sectors of 45 degrees
    assert kawasaki([math.pi / 4] * 8)
    # odd degree fails
    assert not kawasaki([2 * math.pi / 3] * 3)
    # unequal alternating sums fail
    assert not kawasaki([math.radians(a) for a in (100, 80, 100, 80)])
    # generic flat-foldable vertex (alternating sums both 180)
    assert kawasaki([math.radians(a) for a in (100, 80, 80, 100)])


def test_maekawa():
    assert maekawa([MOUNTAIN, MOUNTAIN, MOUNTAIN, VALLEY])
    assert not maekawa([MOUNTAIN, MOUNTAIN, VALLEY, VALLEY])
    assert not maekawa([MOUNTAIN] * 4)


def test_crimp_waterbomb_vertex():
    # classic waterbomb base vertex: 8 creases, alternating M/V except
    # two adjacent mountains twice -> standard assignment MMVMVMVV variants.
    angles = [math.pi / 4] * 8
    # A known-valid waterbomb assignment: alternate M/V but flip one pair
    # to satisfy Maekawa (6M/2V variant is not standard; use 5M/3V).
    asg = [MOUNTAIN, VALLEY, MOUNTAIN, VALLEY, MOUNTAIN, VALLEY, MOUNTAIN, MOUNTAIN]
    assert maekawa(asg)
    assert crimp_foldable(angles, asg)


def test_crimp_big_little_big_violation():
    # Big-little-big lemma: a strict minimum sector bounded by equal
    # assignments is not flat-foldable.
    angles = [math.radians(a) for a in (100, 30, 80, 150)]
    assert kawasaki(angles)
    # sector of 30 deg is a strict local min between creases 1 and 2:
    # give them the same assignment -> must fail
    bad = [VALLEY, MOUNTAIN, MOUNTAIN, MOUNTAIN]
    assert maekawa(bad)
    assert not crimp_foldable(angles, bad)
    # opposite assignments around the minimum -> foldable
    good = [MOUNTAIN, MOUNTAIN, VALLEY, MOUNTAIN]
    assert maekawa(good)
    assert crimp_foldable(angles, good)


def make_single_valley_cp():
    cp = CreasePattern(2.0)
    # border
    for p1, p2 in [((0, 0), (2, 0)), ((2, 0), (2, 2)), ((2, 2), (0, 2)), ((0, 2), (0, 0))]:
        cp.add_crease(p1, p2, BORDER)
    cp.add_crease((1, 0), (1, 2), VALLEY)
    return cp


def test_pattern_check_no_interior_vertices():
    cp = make_single_valley_cp()
    ok, reports = check_pattern(cp.planarize())
    assert ok


def make_bird_base_corner():
    """One corner 'rabbit ear' style vertex from the bird base.

    Interior vertex at center of a 2x2 sheet with creases to the four
    corners (diagonals) and two edge midpoints - a classic flat-foldable
    vertex: angles 45/45/90/90/45/45... simplify: use the standard
    'preliminary fold' center vertex: creases to 4 corners (V) and 4 edge
    midpoints, alternating angles 45 deg.
    """
    cp = CreasePattern(2.0)
    for p1, p2 in [((0, 0), (2, 0)), ((2, 0), (2, 2)), ((2, 2), (0, 2)), ((0, 2), (0, 0))]:
        cp.add_crease(p1, p2, BORDER)
    c = (1, 1)
    # diagonals mountains, orthogonal medians valleys except one flipped
    cp.add_crease(c, (0, 0), MOUNTAIN)
    cp.add_crease(c, (2, 0), MOUNTAIN)
    cp.add_crease(c, (2, 2), MOUNTAIN)
    cp.add_crease(c, (0, 2), MOUNTAIN)
    cp.add_crease(c, (1, 0), VALLEY)
    cp.add_crease(c, (2, 1), VALLEY)
    cp.add_crease(c, (1, 2), VALLEY)
    cp.add_crease(c, (0, 1), MOUNTAIN)
    return cp


def test_pattern_check_waterbomb_center():
    cp = make_bird_base_corner()
    ok, reports = check_pattern(cp.planarize())
    interior = [r for r in reports if r.interior]
    assert len(interior) == 1
    assert ok, [(r.vertex, r.kawasaki, r.maekawa, r.crimp) for r in interior]


def test_pattern_check_detects_maekawa_violation():
    cp = CreasePattern(2.0)
    for p1, p2 in [((0, 0), (2, 0)), ((2, 0), (2, 2)), ((2, 2), (0, 2)), ((0, 2), (0, 0))]:
        cp.add_crease(p1, p2, BORDER)
    c = (1, 1)
    cp.add_crease(c, (0, 0), MOUNTAIN)
    cp.add_crease(c, (2, 0), VALLEY)
    cp.add_crease(c, (2, 2), MOUNTAIN)
    cp.add_crease(c, (0, 2), VALLEY)
    ok, _ = check_pattern(cp.planarize())
    assert not ok
