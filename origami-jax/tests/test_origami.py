"""Regression tests against the committed ground truth extracted from the
original OrigamiSimulator app (groundtruth/crane: model.json, trajectory.json,
renders.json + reference screenshots)."""

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from origami.model import load_model_json
from origami.render import default_camera, render, visible_line_segments
from origami.solver import init_state, make_constants, simulate

GT = Path(__file__).parent.parent / "groundtruth" / "crane"


@pytest.fixture(scope="module")
def model_and_params():
    return load_model_json(str(GT / "model.json"))


@pytest.fixture(scope="module")
def renders():
    with open(GT / "renders.json") as f:
        return json.load(f)


def test_model_load(model_and_params):
    model, params = model_and_params
    assert model.num_nodes == 60
    assert len(model.faces) == 104
    assert len(model.crease_k) == 149
    # original positions are centered and scaled to the unit bounding sphere
    assert np.linalg.norm(model.pos0, axis=1).max() == pytest.approx(1.0, abs=1e-5)
    assert model.dt == pytest.approx(6.66e-3, rel=0.01)
    # nominal triangle angles sum to pi
    np.testing.assert_allclose(model.nominal_angles.sum(axis=1), np.pi, atol=1e-4)


def test_solver_matches_original_trajectory(model_and_params):
    model, params = model_and_params
    with open(GT / "trajectory.json") as f:
        traj = {int(k): np.asarray(v, np.float32).reshape(-1, 3) for k, v in json.load(f).items()}
    c = make_constants(model, params["faceStiffness"])
    state = init_state(model)
    done = 0
    extent = float(np.ptp(model.pos0))
    for n in (1, 10, 100):
        state = simulate(c, state, params["creasePercent"], n - done)
        done = n
        err = np.linalg.norm(np.asarray(state.pos) - traj[n], axis=1).max()
        # the original ran on GPU float32; agreement is a few 1e-4 of the extent
        assert err / extent < 2e-3, f"step {n}: max error {err:.2e}"


def test_camera_matches_threejs(renders):
    r = renders[0]
    view, proj, _ = default_camera(r["width"], r["height"])
    np.testing.assert_allclose(view, np.asarray(r["matrixWorldInverse"]).reshape(4, 4).T, atol=1e-5)
    np.testing.assert_allclose(proj, np.asarray(r["projectionMatrix"]).reshape(4, 4).T, atol=1e-5)


def test_render_matches_original_screenshot(model_and_params, renders):
    model, _ = model_and_params
    r = next(x for x in renders if x["creasePercent"] == 0.6)
    positions = np.asarray(r["positions"], np.float32).reshape(-1, 3)
    img = render(
        positions,
        model.faces,
        visible_line_segments(model.lines),
        width=r["width"],
        height=r["height"],
    )
    ref = np.asarray(Image.open(GT / r["image"]).convert("RGB"))
    diff = np.abs(img.astype(np.int16) - ref.astype(np.int16)).max(axis=2)
    assert np.mean(diff == 0) > 0.95, "expected >=95% of pixels exactly identical"
    assert np.mean(diff <= 2) > 0.99, "expected >=99% of pixels within +-2/255"


def test_end_to_end_fold_and_render(model_and_params):
    model, params = model_and_params
    c = make_constants(model, params["faceStiffness"])
    state = simulate(c, init_state(model), 0.6, 500)
    pos = np.asarray(state.pos)
    assert np.isfinite(pos).all()
    # folding moves the sheet out of plane
    assert np.ptp(pos[:, 1]) > 0.1
    img = render(pos, model.faces, visible_line_segments(model.lines), width=200, height=150)
    assert img.shape == (150, 200, 3)
    assert (img != 255).any(), "render should not be blank"


def test_svg_import_matches_browser_import():
    """The standalone SVG importer must reproduce the original app's import
    (groundtruth/crane/model.json came from the browser importing this SVG)."""
    from origami.model import load_fold
    from origami.svg_import import svg_to_fold

    fold = svg_to_fold(str(Path(__file__).parent.parent / "testdata" / "traditionalCrane.svg"))
    assert not fold["ignored_strokes"]
    ours = load_fold(fold)
    ref, _ = load_model_json(str(GT / "model.json"))
    assert ours.num_nodes == ref.num_nodes == 60
    assert np.abs(ours.pos0 - ref.pos0).max() < 1e-5
    assert {tuple(sorted(e)) for e in ours.edges.tolist()} == {tuple(sorted(e)) for e in ref.edges.tolist()}
    assert {tuple(f) for f in ours.faces.tolist()} == {tuple(f) for f in ref.faces.tolist()}
    assert len(ours.crease_k) == len(ref.crease_k)
    np.testing.assert_allclose(np.sort(ours.crease_k), np.sort(ref.crease_k), atol=1e-4)
