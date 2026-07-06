import numpy as np
import pytest

from corigami.fold import fold
from corigami.pipeline import run_figure
from corigami.shaping import pose
from corigami.stickfigure import example_figures

FIGS = {f.name: f for f in example_figures()}


def test_zero_pose_matches_flat_base():
    """Posing every flap by 0 degrees reproduces the flat-folded base."""
    res = run_figure(FIGS["bird"])
    flat = fold(res.solved_cp)
    posed = pose(res.solved_cp, res.packing,
                 {"left wing": 0, "right wing": 0, "head": 0, "tail": 0})
    # same vertex count, and all z ~ 0 (still collapsed flat)
    assert abs(posed.vertices3d[:, 2]).max() < 1e-9
    assert posed.mean_axial_strain < 1e-9


@pytest.mark.parametrize("name", list(FIGS))
def test_pose_is_isometric(name):
    """Hinge posing stays a rigid, flat-foldable transform (near-zero strain)."""
    sf = FIGS[name]
    res = run_figure(sf)
    deltas = {}
    for i, flap in enumerate(sf.flaps):
        deltas[flap.label] = 50 if i % 2 == 0 else -50
    st = pose(res.solved_cp, res.packing, deltas)
    assert st.mean_axial_strain < 1e-9, st.mean_axial_strain


def test_pose_lifts_flaps_out_of_plane():
    """A nonzero pose actually moves geometry off the base plane."""
    res = run_figure(FIGS["seedling"])
    st = pose(res.solved_cp, res.packing,
              {"left leaf": 55, "right leaf": -55, "root": 90})
    assert np.ptp(st.vertices3d[:, 2]) > 1.0


def test_pose_rejects_river_label():
    res = run_figure(FIGS["bird"])
    with pytest.raises(ValueError):
        pose(res.solved_cp, res.packing, {"body": 40})
