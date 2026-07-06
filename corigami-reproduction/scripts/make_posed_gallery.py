"""Pose the example models via hinge posing and render the gallery.

The pose angles play the role of the paper's shaping orchestration (App. G /
the in-context Gemini baseline): per-flap pivot angles chosen from the stick
figures' limb angles, signs alternated to spread stacked flaps apart.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from pathlib import Path

from corigami.pipeline import run_figure
from corigami.shaping import pose
from corigami.stickfigure import example_figures

OUT = Path(__file__).resolve().parent.parent / "outputs"

POSES = {
    "seedling": {"left leaf": 55, "right leaf": -55, "root": 90},
    "bird": {"left wing": 65, "right wing": -65, "head": 40, "tail": -35},
    "human": {"left arm": 70, "right arm": -70, "left leg": 35,
              "right leg": -35, "head": 50},
    "lizard": {"front left leg": 55, "front right leg": -55,
               "hind left leg": 55, "hind right leg": -55,
               "head": 30, "tail": -15},
    "antenna beetle": {"left antenna": 40, "right antenna": -40,
                       "front left leg": 60, "front right leg": -60,
                       "hind left leg": 60, "hind right leg": -60},
}
BEST_VIEW = {"seedling": (25, -60), "bird": (15, 15), "human": (25, -60),
             "lizard": (40, -100), "antenna beetle": (8, -30)}

fig = plt.figure(figsize=(17, 4.4))
for k, sf in enumerate(example_figures()):
    res = run_figure(sf)
    st = pose(res.solved_cp, res.packing, POSES[sf.name])
    el, az = BEST_VIEW[sf.name]
    ax = fig.add_subplot(1, 5, k + 1, projection="3d")
    pts = st.vertices3d
    polys = [[pts[v] for v in face] for face in st.faces]
    ax.add_collection3d(Poly3DCollection(polys, facecolor="#f2e8c9",
                        edgecolor="#8a7a4e", lw=0.45, alpha=0.97))
    ax.view_init(elev=el, azim=az)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    c, r = (lo + hi) / 2, max((hi - lo).max() / 2, 1e-3)
    ax.set_xlim(c[0]-r, c[0]+r)
    ax.set_ylim(c[1]-r, c[1]+r)
    ax.set_zlim(c[2]-r, c[2]+r)
    ax.set_axis_off()
    ax.set_title(f"{sf.name} (strain {st.mean_axial_strain:.0e})", fontsize=11)
fig.suptitle("Posed models — hinge posing (first slice of the paper's "
             "shaping stage), view-selected", fontsize=13)
fig.tight_layout()
fig.savefig(OUT / "posed-views.png", dpi=140, bbox_inches="tight")
print("outputs/posed-views.png written")
