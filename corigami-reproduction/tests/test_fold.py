import math

import numpy as np
import pytest

from corigami.cp import BORDER, MOUNTAIN, VALLEY, CreasePattern
from corigami.fold import fold


def square_cp(size=2.0):
    cp = CreasePattern(size)
    s = size
    for p1, p2 in [((0, 0), (s, 0)), ((s, 0), (s, s)), ((s, s), (0, s)), ((0, s), (0, 0))]:
        cp.add_crease(p1, p2, BORDER)
    return cp


def test_faces_of_single_crease():
    cp = square_cp()
    cp.add_crease((1, 0), (1, 2), VALLEY)
    faces = cp.planarize().faces()
    assert len(faces) == 2


def test_single_fold_flat():
    cp = square_cp()
    cp.add_crease((1, 0), (1, 2), VALLEY)
    st = fold(cp)
    assert st.mean_axial_strain < 1e-9
    # folded flat: all z ~ 0 and x range halves
    xs = st.vertices3d[:, 0]
    assert np.ptp(xs) < 1.0 + 1e-6


def test_partial_valley_folds_up():
    cp = square_cp()
    cp.add_crease((1, 0), (1, 2), VALLEY)
    st = fold(cp, fold_fraction=0.5)
    # valley: the moving half should rise above the base plane
    assert st.vertices3d[:, 2].max() > 0.1
    assert st.vertices3d[:, 2].min() > -1e-6


def test_partial_mountain_folds_down():
    cp = square_cp()
    cp.add_crease((1, 0), (1, 2), MOUNTAIN)
    st = fold(cp, fold_fraction=0.5)
    assert st.vertices3d[:, 2].min() < -0.1
    assert st.vertices3d[:, 2].max() < 1e-6


def test_waterbomb_center_folds_flat():
    cp = square_cp()
    c = (1, 1)
    cp.add_crease(c, (0, 0), MOUNTAIN)
    cp.add_crease(c, (2, 0), MOUNTAIN)
    cp.add_crease(c, (2, 2), MOUNTAIN)
    cp.add_crease(c, (0, 2), MOUNTAIN)
    cp.add_crease(c, (1, 0), VALLEY)
    cp.add_crease(c, (2, 1), VALLEY)
    cp.add_crease(c, (1, 2), VALLEY)
    cp.add_crease(c, (0, 1), MOUNTAIN)
    st = fold(cp)
    assert st.mean_axial_strain < 1e-9, st.mean_axial_strain
    assert abs(st.vertices3d[:, 2]).max() < 1e-9


def test_strain_detects_nonfoldable():
    # 4 creases meeting at center with non-Kawasaki angles cannot fold flat:
    # the simulator should report nonzero strain.
    cp = square_cp()
    c = (1, 1)
    cp.add_crease(c, (0, 0), MOUNTAIN)
    cp.add_crease(c, (2, 0.5), VALLEY)  # asymmetric -> violates Kawasaki
    cp.add_crease(c, (2, 2), MOUNTAIN)
    cp.add_crease(c, (0, 1.5), VALLEY)
    st = fold(cp)
    assert st.mean_axial_strain > 1e-3
