"""Fast smoke tests for the C.Origami reproduction (no training)."""

import numpy as np
import torch

from corigami_repro.data import SyntheticGenome, make_splits
from corigami_repro.model import DEMO_CONFIG, PAPER_CONFIG, build_model
from corigami_repro import inference, metrics


def test_paper_config_input_length():
    m = build_model(**PAPER_CONFIG)
    assert m.input_length == 2_097_152  # 2 Mb window, 256-bin map
    assert m.map_size == 256


def test_demo_forward_shapes():
    m = build_model(**DEMO_CONFIG)
    x = torch.randn(2, m.input_length, 7)
    y = m(x)
    assert y.shape == (2, m.map_size, m.map_size)


def test_dataset_shapes():
    m = build_model(**DEMO_CONFIG)
    tr, va, te = make_splits(m.input_length, m.map_size, n_train=1, length_bp=40_000)
    x, y = tr[0]
    assert x.shape == (m.input_length, 7)
    assert y.shape == (m.map_size, m.map_size)
    assert np.isfinite(y).all()


def test_synthetic_genome_has_tad_structure():
    g = SyntheticGenome("t", length_bp=40_000, res=64, seed=3)
    assert len(g.boundaries) > 3
    # CTCF signal is elevated at boundaries relative to a random interior point.
    at_boundary = g.ctcf[g.boundaries[2] * g.res]
    assert at_boundary > g.ctcf.mean()


def test_ablation_changes_prediction():
    m = build_model(**DEMO_CONFIG)
    g = SyntheticGenome("t", length_bp=40_000, res=64, seed=5)
    b = int(g.boundaries[len(g.boundaries) // 2])
    boundary_bp = b * g.res
    start = max(0, boundary_bp - m.input_length // 2)
    _, _, diff = inference.ablate_and_predict(m, g, start, boundary_bp - 96, 192, m.input_length)
    assert np.abs(diff).mean() > 0  # ablation perturbs the output


def test_metrics_perfect_prediction():
    rng = np.random.default_rng(0)
    t = rng.random((3, 16, 16)).astype(np.float32)
    t = 0.5 * (t + t.transpose(0, 2, 1))
    s = metrics.summarize(t, t, res=64)
    assert s["mse"] < 1e-6
    assert s["map_pearson"] > 0.999
