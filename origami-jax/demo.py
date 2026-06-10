"""End-to-end pipeline: JAX folding solver -> NumPy renderer.

Folds the model to several percentages with the JAX solver (starting flat,
sweeping upward like the original app's slider), renders each state with the
NumPy renderer, and writes a fold-animation GIF. If reference screenshots
exist, also reports full-pipeline pixel agreement (solver + renderer combined).
"""
import json
import os
import sys

import numpy as np
from PIL import Image

from origami.model import load_model_json
from origami.render import render, visible_line_segments
from origami.solver import init_state, make_constants, simulate

gt_dir = sys.argv[1] if len(sys.argv) > 1 else "groundtruth/crane"
out_dir = sys.argv[2] if len(sys.argv) > 2 else "output"
os.makedirs(out_dir, exist_ok=True)

model, params = load_model_json(f"{gt_dir}/model.json")
c = make_constants(model, params["faceStiffness"])
lines = visible_line_segments(model.lines)
name = os.path.basename(gt_dir.rstrip("/"))

# fold animation: sweep crease percent, settling at each frame
frames = []
state = init_state(model)
for pct in np.linspace(0.0, 0.95, 20):
    state = simulate(c, state, float(pct), 300)
    frames.append(Image.fromarray(render(np.asarray(state.pos), model.faces, lines)))
frames[0].save(f"{out_dir}/{name}_fold.gif", save_all=True, append_images=frames[1:],
               duration=80, loop=0)
print(f"wrote {out_dir}/{name}_fold.gif")

# full-pipeline comparison against reference screenshots (fresh solve per target,
# 3000 settle steps, like extract_groundtruth.js)
ref_path = f"{gt_dir}/renders.json"
if os.path.exists(ref_path):
    with open(ref_path) as f:
        renders = json.load(f)
    for r in renders:
        state = simulate(c, init_state(model), r["creasePercent"], 3000)
        img = render(np.asarray(state.pos), model.faces, lines,
                     width=r["width"], height=r["height"])
        ref = np.asarray(Image.open(f"{gt_dir}/{r['image']}").convert("RGB"))
        diff = np.abs(img.astype(np.int16) - ref.astype(np.int16)).max(axis=2)
        tag = r["image"].removesuffix(".png")
        print(f"full pipeline {tag}: identical {100*np.mean(diff==0):6.2f}%  "
              f"|d|<=2 {100*np.mean(diff<=2):6.2f}%  mean|d| {diff.mean():.3f}")
        Image.fromarray(img).save(f"{out_dir}/{name}_{tag}_pipeline.png")
