"""Compare the JAX solver against the original GPU solver's trajectory.

The ground truth (groundtruth/<name>/trajectory.json) was produced by the actual
OrigamiSimulator app running headless: reset() then step(n), dumping the absolute
node positions at n = 1, 10, 100, 500, 1000 (creasePercent as exported in model.json).

Also benchmarks the jitted solver.
"""

import json
import sys
import time

import jax
import numpy as np

from origami.model import load_model_json
from origami.solver import init_state, make_constants, simulate

gt_dir = sys.argv[1] if len(sys.argv) > 1 else "groundtruth/crane"

model, params = load_model_json(f"{gt_dir}/model.json")
with open(f"{gt_dir}/trajectory.json") as f:
    traj = {int(k): np.asarray(v, dtype=np.float32).reshape(-1, 3) for k, v in json.load(f).items()}

print(
    f"model: {model.num_nodes} nodes, {len(model.edges)} edges, {len(model.faces)} faces, {len(model.crease_k)} creases"
)
print(f"dt={model.dt:.6e}  creasePercent={params['creasePercent']}")

c = make_constants(model, params["faceStiffness"])
pct = params["creasePercent"]

state = init_state(model)
extent = float(np.ptp(model.pos0))  # model spans ~2 units (unit bounding sphere)
done = 0
for n in sorted(traj):
    state = simulate(c, state, pct, n - done)
    done = n
    ours = np.asarray(state.pos)
    ref = traj[n]
    err = np.linalg.norm(ours - ref, axis=1)
    print(
        f"step {n:5d}: max|dp| = {err.max():.3e}  mean|dp| = {err.mean():.3e}  "
        f"(relative to extent: {err.max() / extent:.2e})"
    )

# ---- benchmark ----
state = init_state(model)
state = simulate(c, state, pct, 1)  # compile
jax.block_until_ready(state)
n_bench = 10000
t0 = time.perf_counter()
state = simulate(c, state, pct, n_bench)
jax.block_until_ready(state)
t1 = time.perf_counter()
per_step = (t1 - t0) / n_bench
print(
    f"\nbenchmark ({jax.devices()[0].platform}): {n_bench} steps in {t1 - t0:.3f}s "
    f"-> {per_step * 1e6:.1f} us/step ({1 / per_step:,.0f} steps/s)"
)
