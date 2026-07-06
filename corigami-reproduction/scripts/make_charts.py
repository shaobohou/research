"""Charts for the batch results: survival funnel (Fig. 6 analog) and
failure-stage breakdown by stick count (Fig. 7 analog)."""

import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent.parent / "outputs"
rows = json.loads((OUT / "batch_rows.json").read_text())

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
BLUE, AQUA, YELLOW, RED = "#2a78d6", "#1baf7a", "#eda100", "#e34948"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "text.color": INK, "axes.edgecolor": MUTED,
    "xtick.color": MUTED, "ytick.color": MUTED, "font.size": 10,
})

# ---------------------------------------------------------- survival funnel
n = len(rows)
packed = sum(1 for r in rows if r["stage_reached"] != "packing")
solved = sum(1 for r in rows if r["stage_reached"] in ("folding", "done"))
done = sum(1 for r in rows if r["stage_reached"] == "done")

stages = ["tree candidates", "valid packing", "flat-foldable CP",
          "folded + verified"]
counts = [n, packed, solved, done]

fig, ax = plt.subplots(figsize=(7, 3.2))
ys = range(len(stages))[::-1]
bars = ax.barh(list(ys), counts, height=0.55, color=BLUE, zorder=3)
for y, c, prev in zip(ys, counts, [None] + counts[:-1]):
    pct = "" if prev is None else f"  ({c / prev:.0%} of previous)"
    ax.text(c + n * 0.01, y, f"{c}{pct}", va="center", color=INK, fontsize=10)
ax.set_yticks(list(ys), stages)
ax.set_xlim(0, n * 1.35)
ax.xaxis.grid(True, color=GRID, lw=0.8, zorder=0)
ax.spines[["top", "right", "left"]].set_visible(False)
ax.set_title(
    f"Pipeline survival over {n} random tree candidates "
    f"(overall {done / n:.0%}; paper Fig. 6 reports 5.0% at 560k scale)",
    fontsize=10, loc="left",
)
fig.tight_layout()
fig.savefig(OUT / "pass-rates.png", dpi=150)
plt.close(fig)

# ------------------------------------------------- failure stage by n_sticks
sizes = sorted({r["sticks"] for r in rows})
cats = [
    ("succeeded", lambda r: r["stage_reached"] == "done", BLUE),
    ("failed at packing", lambda r: r["stage_reached"] == "packing", YELLOW),
    ("failed at solving/folding",
     lambda r: r["stage_reached"] in ("solving", "folding"), RED),
]
fig, ax = plt.subplots(figsize=(7, 3.4))
lefts = Counter()
for label, pred, color in cats:
    vals = []
    for s in sizes:
        sub = [r for r in rows if r["sticks"] == s]
        vals.append(sum(1 for r in sub if pred(r)) / len(sub) * 100)
    ax.barh([str(s) for s in sizes], vals,
            left=[lefts[s] for s in sizes], height=0.55, color=color,
            label=label, zorder=3, edgecolor=SURFACE, linewidth=2)
    for s, v in zip(sizes, vals):
        if v >= 8:
            ax.text(lefts[s] + v / 2, str(s), f"{v:.0f}%", ha="center",
                    va="center", color=SURFACE
                    if color == BLUE else INK, fontsize=8.5)
        lefts[s] += v
ax.set_xlim(0, 100)
ax.set_xlabel("share of candidates (%)", color=MUTED)
ax.set_ylabel("sticks in tree", color=MUTED)
ax.spines[["top", "right", "left"]].set_visible(False)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=3,
          frameon=False, fontsize=9)
ax.set_title("Failure stage by structural complexity (paper Fig. 7 analog)",
             fontsize=10, loc="left")
fig.tight_layout()
fig.savefig(OUT / "failure-by-size.png", dpi=150)
plt.close(fig)
print("charts written")
