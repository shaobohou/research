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
from corigami.render import draw_cp, draw_folded, draw_packing, draw_stick_figure
from corigami.stickfigure import example_figures

OUT = Path(__file__).resolve().parent.parent / "outputs"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- examples
summary = []
for sf in example_figures():
    res = run_figure(sf)
    line = {
        "name": sf.name,
        "prompt": sf.prompt,
        "sticks": res.n_sticks,
        "rivers": res.n_rivers,
        "stage_reached": res.stage_reached,
        "error": res.error,
        "grid_heuristic": res.grid_heuristic,
        "grid_used": res.grid_used,
        "mean_strain": res.mean_strain,
        "uniaxial_rms": res.uniaxial_rms,
        "seconds": round(res.seconds, 2),
    }
    summary.append(line)
    print(f"[{sf.name}] stage={res.stage_reached} G={res.grid_used} "
          f"strain={res.mean_strain:.1e} uniax={res.uniaxial_rms:.1e} "
          f"({res.seconds:.1f}s)")
    if not res.ok:
        continue
    slug = sf.name.replace(" ", "-")
    draw_stick_figure(sf, OUT / f"{slug}-stickfigure.png")
    draw_packing(res.packing, OUT / f"{slug}-packing.png",
                 title=f"{sf.name}: packing (grid {res.grid_used})")
    cp, kinds = res.solved_cp, res.kinds
    draw_cp(cp, OUT / f"{slug}-cp.png",
            title=f"{sf.name}: solved CP (M=red, V=blue dashed)")
    # folded flat (the base) and partially folded (for the 7-view judge)
    draw_folded(res.folded, OUT / f"{slug}-folded-flat.png",
                title=f"{sf.name}: flat-folded base (layers separated)",
                layer_eps=0.06)
    partial = fold(cp, fold_fraction=0.92)
    draw_folded(partial, OUT / f"{slug}-folded-views.png",
                title=f"{sf.name}: folded model, 7 views (92% fold)")

(OUT / "examples.json").write_text(json.dumps(summary, indent=2))

# ------------------------------------------------------------ random batch
n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
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
