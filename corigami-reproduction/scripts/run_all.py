"""Generate all outputs: example artifacts + random-batch pass rates.

Usage: uv run python scripts/run_all.py [n_random]
"""

import json
import random
import sys
from collections import Counter
from pathlib import Path

from corigami.fold import fold
from corigami.pipeline import random_figure, run_figure
from corigami.render import draw_cp, draw_packing, draw_stick_figure
from corigami.render3d import render
from corigami.shaping import pose, pose_angles_from_figure
from corigami.stickfigure import example_figures

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent.parent / "outputs"
OUT.mkdir(exist_ok=True)

SEVEN_VIEWS = [("front", 8, 25), ("side", 15, 105), ("top", 62, -70),
               ("iso a", 30, -100), ("iso b", 18, -55), ("iso c", 50, -70),
               ("rear", 28, 160)]

# ---------------------------------------------------------------- examples
summary = []
for sf in example_figures():
    res = run_figure(sf)
    line = {
        "name": sf.name, "prompt": sf.prompt,
        "sticks": res.n_sticks, "rivers": res.n_rivers,
        "stage_reached": res.stage_reached, "error": res.error,
        "grid_heuristic": res.grid_heuristic, "grid_used": res.grid_used,
        "mean_strain": res.mean_strain, "uniaxial_rms": res.uniaxial_rms,
        "layers": round(res.layers, 1), "seconds": round(res.seconds, 2),
    }
    summary.append(line)
    print(f"[{sf.name}] stage={res.stage_reached} G={res.grid_used}"
          f"(h{res.grid_heuristic}) strain={res.mean_strain:.1e} "
          f"layers={res.layers:.0f} ({res.seconds:.1f}s)", flush=True)
    if not res.ok:
        continue
    slug = sf.name.replace(" ", "-")
    draw_stick_figure(sf, OUT / f"{slug}-stickfigure.png")
    draw_packing(res.packing, OUT / f"{slug}-packing.png",
                 title=f"{sf.name}: packing (grid {res.grid_used})")
    draw_cp(res.solved_cp, OUT / f"{slug}-cp.png",
            title=f"{sf.name}: solved CP (M=red, V=blue dashed)")

    angles = pose_angles_from_figure(res.solved_cp, res.packing, sf)
    posed = pose(res.solved_cp, res.packing, angles)
    line["posed_strain"] = posed.mean_axial_strain
    fig, axes = plt.subplots(2, 4, figsize=(14, 7), facecolor="white")
    for ax, (name, el, az) in zip(axes.ravel(), SEVEN_VIEWS):
        render(ax, posed.vertices3d, posed.faces, el, az)
        ax.set_title(name, fontsize=9)
    axes.ravel()[-1].axis("off")
    fig.suptitle(f"{sf.name} — {sf.prompt}", fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT / f"{slug}-folded-views.png", dpi=140)
    plt.close(fig)

(OUT / "examples.json").write_text(json.dumps(summary, indent=2))

# ------------------------------------------------------------ random batch
n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
if n == 0:
    print("skipping random batch"); raise SystemExit
rng = random.Random(2606)
stage_counter = Counter()
per_size: dict[int, Counter] = {}
rows = []
for i in range(n):
    sf = random_figure(rng, i)
    res = run_figure(sf, g_max_extra=4, max_solutions=1, time_budget=20.0)
    stage_counter[res.stage_reached] += 1
    per_size.setdefault(res.n_sticks, Counter())[res.stage_reached] += 1
    rows.append({
        "name": res.name, "sticks": res.n_sticks, "rivers": res.n_rivers,
        "stage_reached": res.stage_reached, "grid_used": res.grid_used,
        "error": res.error, "seconds": round(res.seconds, 2),
    })
    if (i + 1) % 10 == 0:
        print(f"batch {i+1}/{n}: {dict(stage_counter)}", flush=True)
        (OUT / "batch_rows.json").write_text(json.dumps(rows, indent=2))

# survival table (paper Fig. 6 analog)
n_pack_attempted = n
n_packed = sum(1 for r in rows if r["stage_reached"] not in ("packing",))
n_solved = sum(
    1 for r in rows if r["stage_reached"] in ("folding", "done")
)
n_done = stage_counter["done"]
stats = {
    "n_candidates": n,
    "packing_pass": n_packed,
    "packing_rate": n_packed / n,
    "solving_pass": n_solved,
    "solving_rate": n_solved / max(n_packed, 1),
    "folding_pass": n_done,
    "folding_rate": n_done / max(n_solved, 1),
    "overall_rate": n_done / n,
    "by_stage": dict(stage_counter),
    "by_n_sticks": {k: dict(v) for k, v in sorted(per_size.items())},
}
(OUT / "batch_stats.json").write_text(json.dumps(stats, indent=2))
(OUT / "batch_rows.json").write_text(json.dumps(rows, indent=2))
print(json.dumps(stats, indent=2))
