"""Hero gallery: pose each example via the stick figure and render one best view."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from corigami.pipeline import run_figure
from corigami.render3d import render
from corigami.shaping import pose, pose_angles_from_figure
from corigami.stickfigure import example_figures

OUT = Path(__file__).resolve().parent.parent / "outputs"

# view chosen per model, as the paper picks a best angle before judging
BEST_VIEW = {
    "bird": (30, -100), "crab": (50, -70), "dragonfly": (30, -100),
    "starfish": (35, -95), "seedling": (30, -100), "lizard": (45, -85),
}

figs = example_figures()
cols = 3
rows = (len(figs) + cols - 1) // cols
fig, axes = plt.subplots(rows, cols, figsize=(4.6 * cols, 4.4 * rows),
                         facecolor="white")
for ax, sf in zip(axes.ravel(), figs):
    res = run_figure(sf)
    angles = pose_angles_from_figure(res.solved_cp, res.packing, sf)
    st = pose(res.solved_cp, res.packing, angles)
    el, az = BEST_VIEW.get(sf.name, (30, -100))
    render(ax, st.vertices3d, st.faces, el, az)
    ax.set_title(f"{sf.name} — “{sf.prompt}”\ngrid {res.grid_used} · "
                 f"{res.layers:.0f} layers · strain {st.mean_axial_strain:.0e}",
                 fontsize=9.5)
for ax in axes.ravel()[len(figs):]:
    ax.axis("off")
fig.suptitle("COrigami reproduction — posed models from text prompts "
             "(every model verified flat-foldable and folded isometrically)",
             fontsize=13)
fig.tight_layout(rect=(0, 0, 1, 0.955))
fig.savefig(OUT / "posed-views.png", dpi=150, bbox_inches="tight")
print("outputs/posed-views.png written")
