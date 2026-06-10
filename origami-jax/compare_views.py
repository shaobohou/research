"""Compare the NumPy renderer against the original from multiple camera angles.

Uses groundtruth/<name>_views/views.json (extract_views.js): one settled fold
state, screenshots + exact camera matrices for the iso and six axis views.
Renders each view with the dumped matrices, verifies our analytic camera
(look_at_inverse, including the degenerate top/bottom handling) reproduces
them, and writes per-view comparison images plus a contact sheet.
"""

import json
import os
import sys

import numpy as np
from PIL import Image

from origami.model import load_model_json
from origami.render import CAMERA, look_at_inverse, render, visible_line_segments

gt_dir = sys.argv[1] if len(sys.argv) > 1 else "groundtruth/crane_views"
model_json = sys.argv[2] if len(sys.argv) > 2 else "groundtruth/crane/model.json"
out_dir = sys.argv[3] if len(sys.argv) > 3 else "output"
os.makedirs(out_dir, exist_ok=True)

model, _ = load_model_json(model_json)
lines = visible_line_segments(model.lines)
with open(f"{gt_dir}/views.json") as f:
    data = json.load(f)

name = os.path.basename(gt_dir.rstrip("/"))
positions = np.asarray(data["positions"], np.float32).reshape(-1, 3)
W, H = data["width"], data["height"]
dist = float(np.linalg.norm(CAMERA["position"]))  # camera orbit radius (sqrt(75))

rows = []
for v in data["views"]:
    view_ref = np.asarray(v["matrixWorldInverse"]).reshape(4, 4).T
    proj_ref = np.asarray(v["projectionMatrix"]).reshape(4, 4).T
    cam_pos = np.asarray(v["cameraPosition"])

    # our analytic camera (TrackballControls.reset keeps the orbit radius)
    view_ours = look_at_inverse(cam_pos, CAMERA["target"], CAMERA["up"])
    assert np.allclose(view_ours, view_ref, atol=1e-5), f"{v['name']}: camera mismatch"
    assert abs(np.linalg.norm(cam_pos) - dist) < 1e-4, v["name"]

    img = render(positions, model.faces, lines, width=W, height=H, view=view_ref, proj=proj_ref, camera_pos=cam_pos)
    ref = np.asarray(Image.open(f"{gt_dir}/{v['image']}").convert("RGB"))
    diff = np.abs(img.astype(np.int16) - ref.astype(np.int16)).max(axis=2)
    print(
        f"{name} {v['name']:6s}: identical {100 * np.mean(diff == 0):6.2f}%  "
        f"|d|<=2 {100 * np.mean(diff <= 2):6.2f}%  mean|d| {diff.mean():6.3f}"
    )
    Image.fromarray(np.concatenate([ref, img], axis=1)).save(f"{out_dir}/{name}_{v['name']}_side_by_side.png")
    rows.append((ref, img, diff))

# contact sheet: columns = views, row 1 = original, row 2 = numpy, row 3 = diff heat
scale = 4
thumbs = []
for ref, img, diff in rows:
    heat = np.zeros_like(ref)
    heat[..., 0] = np.clip(diff.astype(np.int32) * 8, 0, 255)
    col = np.concatenate([ref, img, heat], axis=0)
    thumbs.append(np.asarray(Image.fromarray(col).reduce(scale)))
Image.fromarray(np.concatenate(thumbs, axis=1)).save(f"{out_dir}/{name}_contact_sheet.png")
print(f"wrote {out_dir}/{name}_contact_sheet.png")
