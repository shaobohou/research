"""Compare the NumPy renderer against reference screenshots of the original app.

Uses the exact vertex positions and camera matrices dumped alongside each
reference PNG (renders.json), so this isolates the renderer from solver drift.
Also asserts that our analytically-derived camera matrices match the ones
three.js computed in the browser.
"""

import json
import os
import sys

import numpy as np
from PIL import Image

from origami.model import load_model_json
from origami.render import default_camera, render, visible_line_segments

gt_dir = sys.argv[1] if len(sys.argv) > 1 else "groundtruth/crane"
out_dir = sys.argv[2] if len(sys.argv) > 2 else "output"

model, params = load_model_json(f"{gt_dir}/model.json")
with open(f"{gt_dir}/renders.json") as f:
    renders = json.load(f)

lines = visible_line_segments(model.lines)

for r in renders:
    W, H = r["width"], r["height"]
    view, proj, cam_pos = default_camera(W, H)
    # three.js stores matrices column-major
    view_ref = np.asarray(r["matrixWorldInverse"]).reshape(4, 4).T
    proj_ref = np.asarray(r["projectionMatrix"]).reshape(4, 4).T
    assert np.allclose(view, view_ref, atol=1e-5), f"view mismatch:\n{view}\n{view_ref}"
    assert np.allclose(proj, proj_ref, atol=1e-5), f"proj mismatch:\n{proj}\n{proj_ref}"

    positions = np.asarray(r["positions"], dtype=np.float32).reshape(-1, 3)
    img = render(
        positions,
        model.faces,
        lines,
        width=W,
        height=H,
        view=view_ref,
        proj=proj_ref,
        camera_pos=np.asarray(r["cameraPosition"]),
    )

    ref = np.asarray(Image.open(f"{gt_dir}/{r['image']}").convert("RGB"))
    diff = np.abs(img.astype(np.int16) - ref.astype(np.int16)).max(axis=2)

    name = os.path.basename(gt_dir.rstrip("/")) + "_" + r["image"].removesuffix(".png")

    def pct(t):
        return 100.0 * np.mean(diff <= t)

    print(
        f"{name}: identical {pct(0):6.2f}%  |d|<=2 {pct(2):6.2f}%  "
        f"|d|<=8 {pct(8):6.2f}%  mean|d| {diff.mean():6.3f}  max|d| {diff.max()}"
    )

    Image.fromarray(img).save(f"{out_dir}/{name}_numpy.png")
    side = np.concatenate([ref, img], axis=1)
    Image.fromarray(side).save(f"{out_dir}/{name}_side_by_side.png")
    heat = np.zeros_like(ref)
    heat[..., 0] = np.clip(diff * 8, 0, 255)
    Image.fromarray(heat).save(f"{out_dir}/{name}_diff.png")
