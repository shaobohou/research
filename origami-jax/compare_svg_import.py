"""Validate the standalone SVG importer against the original app's import.

For each model with browser-extracted ground truth (groundtruth/<name>/
model.json came from the original's own SVG importer running headless):
  1. svg_to_fold + load_fold and compare structure: vertex positions, edge
     sets, face sets, crease tables (crease orientation flips are physically
     identical -- the crease vector and both face/vertex pairs swap together --
     and are accepted),
  2. run the full browser-free pipeline (SVG -> solve -> render) and compare
     pixels against the original's reference screenshot at 60% fold.

Usage: uv run compare_svg_import.py [svg_assets_root]
"""

import json
import sys

import numpy as np
from PIL import Image

from origami.model import load_fold, load_model_json
from origami.render import render, visible_line_segments
from origami.solver import init_state, make_constants, simulate
from origami.svg_import import svg_to_fold

assets = sys.argv[1] if len(sys.argv) > 1 else "/tmp/OrigamiSimulator/assets"

MODELS = [
    ("crane", "Origami/traditionalCrane.svg"),
    ("hypar", "Origami/hypar.svg"),
    ("waterbomb", "Tessellations/huffmanWaterbomb.svg"),
    ("orchid", "Origami/langOrchid.svg"),
    ("bistable", "Bistable/curvedPleatSimple.svg"),
]


def crease_map(m):
    """Crease table keyed by (sorted edge), canonicalized over orientation:
    a crease traversed from the other side swaps node1/node2 and node3/node4
    in tandem, which is the same physical constraint. Values are exact node
    tuples plus float (k, target) compared with tolerance below."""
    out = {}
    for i in range(len(m.crease_k)):
        n1, n2, n3, n4 = m.crease_nodes[i].tolist()
        if n1 > n2:
            n1, n2, n3, n4 = n2, n1, n4, n3
        out[tuple(sorted((n3, n4)))] = ((n1, n2, n3, n4), float(m.crease_k[i]), float(m.crease_target[i]))
    return out


def creases_equal(a, b, k_tol=1e-4):
    return a is not None and b is not None and a[0] == b[0] and abs(a[1] - b[1]) <= k_tol and abs(a[2] - b[2]) <= 1e-5


for name, svg in MODELS:
    fold = svg_to_fold(f"{assets}/{svg}")
    ours = load_fold(fold)
    ref, params = load_model_json(f"groundtruth/{name}/model.json")

    assert ours.num_nodes == ref.num_nodes, f"{name}: node count"
    pos_err = float(np.abs(ours.pos0 - ref.pos0).max())
    edges_ok = {tuple(sorted(e)) for e in ours.edges.tolist()} == {tuple(sorted(e)) for e in ref.edges.tolist()}
    faces_ok = {tuple(f) for f in ours.faces.tolist()} == {tuple(f) for f in ref.faces.tolist()}
    cm_ours, cm_ref = crease_map(ours), crease_map(ref)
    crease_diffs = sum(1 for k in cm_ours if not creases_equal(cm_ours[k], cm_ref.get(k)))

    r = json.load(open(f"groundtruth/{name}/renders.json"))[2]  # 60% fold
    state = simulate(make_constants(ours, params["faceStiffness"]), init_state(ours), r["creasePercent"], 3000)
    img = render(
        np.asarray(state.pos),
        ours.faces,
        visible_line_segments(ours.lines),
        width=r["width"],
        height=r["height"],
    )
    ref_img = np.asarray(Image.open(f"groundtruth/{name}/{r['image']}").convert("RGB"))
    diff = np.abs(img.astype(np.int16) - ref_img.astype(np.int16)).max(axis=2)

    print(
        f"{name:10s} pos diff {pos_err:.1e}  edges {'OK' if edges_ok else 'DIFF'}  "
        f"faces {'OK' if faces_ok else 'DIFF'}  crease diffs {crease_diffs}/{len(cm_ours)}  |  "
        f"svg->solve->render: exact {100 * np.mean(diff == 0):5.2f}%  "
        f"+-2 {100 * np.mean(diff <= 2):5.2f}%"
    )
