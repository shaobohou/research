import math

import numpy as np
import pytest

from corigami.pipeline import run_figure
from corigami.similarity import tree_similarity
from corigami.stickfigure import example_figures, grid_size_heuristic


@pytest.mark.parametrize("fig", example_figures(), ids=lambda f: f.name)
def test_examples_end_to_end(fig):
    res = run_figure(fig)
    assert res.ok, f"{fig.name}: stage={res.stage_reached} err={res.error}"
    assert res.mean_strain < 1e-9
    assert res.uniaxial_rms < 1e-6, res.uniaxial_rms


def test_grid_heuristic_reasonable():
    for fig in example_figures():
        g = grid_size_heuristic(fig)
        assert g >= fig.diameter()


def test_tree_similarity_invariances():
    rng = np.random.default_rng(0)
    pts = rng.normal(size=(6, 3))
    # rigid rotation + translation + scale => perfect score
    theta = 0.7
    R = np.array(
        [
            [math.cos(theta), -math.sin(theta), 0],
            [math.sin(theta), math.cos(theta), 0],
            [0, 0, 1],
        ]
    )
    moved = 2.5 * pts @ R.T + np.array([1, 2, 3])
    assert tree_similarity(pts, moved) > 1 - 1e-9
    # unrelated point sets => clearly lower score
    other = rng.normal(size=(6, 3))
    assert tree_similarity(pts, other) < 0.95
