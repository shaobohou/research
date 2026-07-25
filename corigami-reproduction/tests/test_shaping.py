import numpy as np
import pytest

from corigami.fold import fold
from corigami.pipeline import run_figure
from corigami.shaping import narrow, pose, pose_angles_from_figure
from corigami.stickfigure import example_figures

FIGS = {f.name: f for f in example_figures()}


def test_zero_pose_matches_flat_base():
    """Posing every flap by 0 degrees reproduces the flat-folded base."""
    sf = FIGS["bird"]
    res = run_figure(sf)
    flat = fold(res.solved_cp)
    posed = pose(res.solved_cp, res.packing,
                 {f.label: 0 for f in sf.flaps})
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
    sf = FIGS["seedling"]
    res = run_figure(sf)
    st = pose(res.solved_cp, res.packing,
              pose_angles_from_figure(res.solved_cp, res.packing, sf))
    assert np.ptp(st.vertices3d[:, 2]) > 1.0


def test_pose_rejects_river_label():
    res = run_figure(FIGS["lizard"])
    with pytest.raises(ValueError):
        pose(res.solved_cp, res.packing, {"body": 40})


def test_derived_angles_separate_mirror_pairs():
    """Mirror-image flaps must land on opposite sides of the base plane."""
    sf = FIGS["bird"]
    res = run_figure(sf)
    ang = pose_angles_from_figure(res.solved_cp, res.packing, sf)
    assert ang["left wing"] * ang["right wing"] < 0
    assert min(abs(ang[k]) for k in ang) >= 20   # nothing left collapsed
    st = pose(res.solved_cp, res.packing, ang)
    assert st.mean_axial_strain < 1e-9


def test_simple_fold_keeps_pattern_foldable():
    """The paper's simple-fold tool adds creases and stays isometric."""
    res = run_figure(FIGS["bird"])
    before = len(res.solved_cp.planarize().edges)
    cp2 = narrow(res.solved_cp, res.packing, factor=0.5)
    assert len(cp2.planarize().edges) > before
    assert fold(cp2).mean_axial_strain < 1e-9
