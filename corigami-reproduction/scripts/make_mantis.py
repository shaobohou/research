"""Best-effort praying mantis, end to end through the whole pipeline.

Exercises every implemented stage: a semantic stick figure with a river
(thorax) separating the front joint (head + raptorial forelegs) from the rear
joint (walking legs + abdomen); discrete packing; crease construction and M/V
solving; the paper's simple-fold tool (§3.5) applied selectively to the two
forelegs to give them the mantis's bent raptorial kink; and hinge posing.

Every stage is verified: all interior vertices flat-foldable, and both the
folded base and the shaped/posed model isometric to ~1e-16 axial strain.

The pose angles stand in for the paper's RL orchestration. Note they are not
mirror-paired: both forelegs are raised to the same side, which single-hinge
posing allows and which is what makes the "praying" posture read.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from corigami.cp import MOUNTAIN
from corigami.fold import fold
from corigami.foldability import check_pattern
from corigami.pipeline import run_figure
from corigami.render import draw_cp, draw_packing
from corigami.render3d import render
from corigami.shaping import pose, simple_fold
from corigami.stickfigure import Stick, StickFigure

OUT = Path(__file__).resolve().parent.parent / "outputs"

FIGURE = StickFigure(
    name="mantis",
    prompt="a praying mantis with raised raptorial forelegs and a long abdomen",
    sticks=[
        Stick("head", 1, 2, 2, 0, 10),
        Stick("left foreleg", 1, 3, 4, 35, 60),
        Stick("right foreleg", 1, 4, 4, -35, 60),
        Stick("thorax", 1, 0, 1, 180, 0),          # river
        Stick("left leg", 0, 5, 2, 120, -55),
        Stick("right leg", 0, 6, 2, -120, -55),
        Stick("abdomen", 0, 7, 5, 180, -20),
    ],
)

BEND_FRACTION = 0.35          # where along the axis the foreleg kink sits
POSE = {                      # degrees about each flap's base hinge
    "abdomen": 5, "head": 168,
    "left foreleg": 140, "right foreleg": 120,
    "left leg": -50, "right leg": -70,
}
VIEWS = [("profile", 18, -90), ("low profile", 6, -90),
         ("three-quarter", 20, -70), ("head-on", 12, -20),
         ("top", 55, -85), ("rear", 15, 120)]


def main() -> None:
    res = run_figure(FIGURE, g_max_extra=4, max_solutions=1, time_budget=60.0)
    if not res.ok:
        raise SystemExit(f"pipeline failed at {res.stage_reached}: {res.error}")
    base_cp = res.solved_cp
    print(f"packed  : grid {res.grid_used} (heuristic {res.grid_heuristic}), "
          f"{res.layers:.0f} layers")
    print(f"base    : {len(base_cp.planarize().edges)} creases, "
          f"strain {res.mean_strain:.1e}, uniaxiality {res.uniaxial_rms:.1e}")

    # --- shaping: bend both raptorial forelegs with one selective simple fold
    flat = fold(base_cp)
    xy = flat.vertices3d[:, :2]
    centred = xy - xy.mean(0)
    _, _, Vt = np.linalg.svd(centred, full_matrices=False)
    axis = Vt[0]
    perp = np.array([-axis[1], axis[0]])
    u = centred @ axis
    cut = xy.mean(0) + (u.min() + BEND_FRACTION * (u.max() - u.min())) * axis
    shaped = simple_fold(base_cp, res.packing, cut, perp, MOUNTAIN,
                         labels=["left foreleg", "right foreleg"])
    n_added = len(shaped.planarize().edges) - len(base_cp.planarize().edges)
    shaped_flat = fold(shaped)
    print(f"shaped  : +{n_added} foreleg creases, "
          f"strain {shaped_flat.mean_axial_strain:.1e}")

    ok, reports = check_pattern(shaped.planarize())
    bad = [r for r in reports if not r.flat_foldable]
    print(f"checks  : flat-foldable at every interior vertex: {ok} "
          f"({len(bad)} failures)")

    posed = pose(shaped, res.packing, POSE)
    print(f"posed   : strain {posed.mean_axial_strain:.1e}, "
          f"max {posed.max_axial_strain:.1e}")

    # --- renders
    draw_packing(res.packing, OUT / "mantis-packing.png",
                 title=f"mantis: packing (grid {res.grid_used})")
    draw_cp(shaped, OUT / "mantis-cp.png",
            title="mantis: shaped crease pattern (M=red, V=blue dashed)")

    fig, axes = plt.subplots(2, 3, figsize=(15, 9), facecolor="white")
    for ax, (name, el, az) in zip(axes.ravel(), VIEWS):
        render(ax, posed.vertices3d, posed.faces, el, az)
        ax.set_title(name, fontsize=10)
    fig.suptitle(f"mantis — “{FIGURE.prompt}”\ngrid {res.grid_used} · "
                 f"{res.layers:.0f} layers · every vertex flat-foldable · "
                 f"posed strain {posed.mean_axial_strain:.0e}", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(OUT / "mantis-views.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 6), facecolor="white")
    render(ax, posed.vertices3d, posed.faces, 18, -90, edge_width=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "mantis-hero.png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    print("wrote outputs/mantis-{hero,views,cp,packing}.png")


if __name__ == "__main__":
    main()
