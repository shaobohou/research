"""End-to-end mini pipeline + pass-rate accounting (paper §4.2, Fig. 6/7).

Stages: stick figure -> grid heuristic + sweep -> packing -> crease
construction -> M/V solving -> local flat-foldability verification ->
geometric folding + strain check -> uniaxiality check -> renders.

The uniaxiality check is an extra verification specific to this
reproduction: in a folded uniaxial base every point's position along the
base axis equals its elevation (up to a planar isometry), so we fit
``u . f(p) = e(p) - c`` by least squares over all vertices and report the
RMS residual. A correct base has residual ~ 0 on top of ~0 axial strain.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field

import numpy as np

from .fold import fold
from .foldability import check_pattern
from .packing import Packing, PackingError, pack_sweep
from .solver import SolveError, assign_mv, build_crease_pattern
from .stickfigure import Stick, StickFigure, grid_size_heuristic


@dataclass
class RunResult:
    name: str
    n_sticks: int = 0
    n_rivers: int = 0
    stage_reached: str = "start"     # packing | solving | folding | done
    error: str = ""
    grid_heuristic: int = 0
    grid_used: int = 0
    mean_strain: float = float("nan")
    max_strain: float = float("nan")
    uniaxial_rms: float = float("nan")
    layers: float = float("nan")
    seconds: float = 0.0
    packing: Packing | None = None
    solved_cp: object = None
    kinds: dict | None = None
    folded: object = None

    @property
    def ok(self) -> bool:
        return self.stage_reached == "done"


def elevation_at(pk: Packing, x: float, y: float) -> float:
    for r in pk.regions:
        x0, y0, x1, y1 = r.rect
        if x0 - 1e-9 <= x <= x1 + 1e-9 and y0 - 1e-9 <= y <= y1 + 1e-9:
            return r.elevation(x, y)
    raise ValueError(f"point ({x},{y}) not in any region")


def uniaxiality_rms(pk: Packing, cp, folded) -> float:
    """RMS deviation from uniaxiality of the folded base.

    In a folded uniaxial base each region's paper projects rigidly onto the
    axis: u . f(p) = s_r * e(p) + c_r with a common axis direction u and a
    per-region sign s_r (edges of the tree may fold back on themselves along
    the axis). u is the folded image of the elevation gradient; since the
    root face is folded with the identity, we read it off that face's region.
    """
    pts2 = np.array(cp.vertices)
    pts3 = folded.vertices3d

    # axis direction from the root face's region (identity transform)
    f0 = folded.faces[0]
    cx, cy = np.mean([pts2[v] for v in f0], axis=0)
    reg0 = next(
        r for r in pk.regions
        if r.rect[0] <= cx <= r.rect[2] and r.rect[1] <= cy <= r.rect[3]
    )
    h = 1e-4
    gx = (reg0.elevation(cx + h, cy) - reg0.elevation(cx - h, cy)) / (2 * h)
    gy = (reg0.elevation(cx, cy + h) - reg0.elevation(cx, cy - h)) / (2 * h)
    u = np.array([gx, gy]) / math.hypot(gx, gy)

    proj = pts3[:, :2] @ u
    sq_sum, n = 0.0, 0
    for r in pk.regions:
        x0, y0, x1, y1 = r.rect
        vids = [
            i for i, (x, y) in enumerate(pts2)
            if x0 - 1e-9 <= x <= x1 + 1e-9 and y0 - 1e-9 <= y <= y1 + 1e-9
        ]
        e = np.array([r.elevation(*pts2[i]) for i in vids])
        p = proj[vids]
        best = min(
            np.sum((p - s * e - np.mean(p - s * e)) ** 2) for s in (1.0, -1.0)
        )
        sq_sum += best
        n += len(vids)
    return float(np.sqrt(sq_sum / max(n, 1)))


def run_figure(sf: StickFigure, g_max_extra: int = 6,
               max_solutions: int = 2,
               time_budget: float | None = None) -> RunResult:
    res = RunResult(name=sf.name, n_sticks=len(sf.sticks),
                    n_rivers=len(sf.rivers))
    t0 = time.time()
    try:
        if sf.validate():
            res.error = "; ".join(sf.validate())
            return res
        res.grid_heuristic = grid_size_heuristic(sf)
        res.stage_reached = "packing"
        G, packs = pack_sweep(sf, res.grid_heuristic, g_max_extra,
                              max_solutions, time_budget=time_budget)
        if not packs:
            res.error = "no valid packing in grid sweep"
            return res
        res.grid_used = G

        last_err = "M/V assignment failed"
        for pk in packs:
            res.stage_reached = "solving"
            try:
                cp, kinds = build_crease_pattern(pk)
                cpp = cp.planarize()
                solved = assign_mv(cpp)
            except SolveError as e:
                last_err = str(e)
                continue
            if solved is None:
                continue
            ok, _ = check_pattern(solved)
            if not ok:
                last_err = "local flat-foldability check failed"
                continue

            res.stage_reached = "folding"
            st = fold(solved)
            res.mean_strain = st.mean_axial_strain
            res.max_strain = st.max_axial_strain
            if st.mean_axial_strain > 1e-6:
                last_err = f"fold strain {st.mean_axial_strain:.2e}"
                continue
            res.uniaxial_rms = uniaxiality_rms(pk, solved, st)
            bb = st.vertices3d.max(0) - st.vertices3d.min(0)
            foot = max(bb[0], 1e-9) * max(bb[1], 1e-9)
            res.layers = float(G * G / foot)   # paper area / folded footprint
            res.packing = pk
            res.solved_cp = solved
            res.kinds = kinds
            res.folded = st
            res.stage_reached = "done"
            res.error = ""
            return res
        res.error = last_err
        return res
    except (PackingError, SolveError, ValueError) as e:
        res.error = f"{type(e).__name__}: {e}"
        return res
    finally:
        res.seconds = time.time() - t0


# --------------------------------------------------------------------------
# Random tree candidates (paper's large-scale sampling, miniaturised)
# --------------------------------------------------------------------------

def random_figure(rng: random.Random, idx: int) -> StickFigure:
    """Random tree in the supported class: star, or two stars + one river."""
    sticks: list[Stick] = []
    if rng.random() < 0.4:
        # star: one joint, 3-6 flaps
        n = rng.randint(3, 6)
        for i in range(n):
            sticks.append(
                Stick(f"flap{i}", 0, i + 1, rng.randint(1, 4),
                      rng.uniform(0, 360), rng.uniform(-60, 60))
            )
    else:
        # two stars joined by a river
        k = rng.randint(1, 2)
        n1, n2 = rng.randint(2, 4), rng.randint(1, 3)
        node = 2
        for i in range(n1):
            sticks.append(
                Stick(f"a{i}", 0, node, rng.randint(1, 4),
                      rng.uniform(0, 360), rng.uniform(-60, 60))
            )
            node += 1
        sticks.append(Stick("river", 0, 1, k, rng.uniform(0, 360), 0.0))
        for i in range(n2):
            sticks.append(
                Stick(f"b{i}", 1, node, rng.randint(1, 4),
                      rng.uniform(0, 360), rng.uniform(-60, 60))
            )
            node += 1
    return StickFigure(name=f"random-{idx}", prompt="random tree candidate",
                       sticks=sticks)
