"""Rendering: crease patterns, packings, stick figures, folded 3D models.

Conventions follow the paper's Fig. 4: packing plots show hinge creases in
green and ridge creases in red; solved crease patterns show mountains in
red and valleys in blue. Folded models are rendered from seven perspectives
(as fed to the VLM judge in §3.8).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from .cp import BORDER, MOUNTAIN, VALLEY, CreasePattern
from .fold import FoldedState
from .packing import Packing
from .solver import HINGE, PLEAT, RIDGE
from .stickfigure import StickFigure

MV_COLORS = {MOUNTAIN: "#d62728", VALLEY: "#1f77b4", BORDER: "#222222"}
KIND_COLORS = {HINGE: "#2ca02c", RIDGE: "#d62728", PLEAT: "#999999"}

SEVEN_VIEWS = [
    ("front", 0, 0),
    ("back", 0, 180),
    ("left", 0, 90),
    ("right", 0, -90),
    ("top", 89, -90),
    ("bottom", -89, -90),
    ("isometric", 30, -60),
]


def draw_cp(cp: CreasePattern, path: str, kinds: dict | None = None,
            title: str = "") -> None:
    """Solved CP (M red / V blue) or, with ``kinds``, a packing-stage CP."""
    fig, ax = plt.subplots(figsize=(5, 5))
    for a, b, asg in cp.edges:
        p1, p2 = cp.vertices[a], cp.vertices[b]
        if kinds is not None and asg not in (MOUNTAIN, VALLEY, BORDER):
            key = _seg_key(p1, p2)
            color = KIND_COLORS.get(kinds.get(key, PLEAT), "#999999")
            style = "-"
        else:
            color = MV_COLORS.get(asg, "#999999")
            style = "-" if asg != VALLEY else "--"
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], style, color=color, lw=1.4)
    ax.set_aspect("equal")
    ax.set_xlim(-0.3, cp.size + 0.3)
    ax.set_ylim(-0.3, cp.size + 0.3)
    ax.set_title(title)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _seg_key(p1, p2):
    a = (round(p1[0] * 4) / 4, round(p1[1] * 4) / 4)
    b = (round(p2[0] * 4) / 4, round(p2[1] * 4) / 4)
    return (min(a, b), max(a, b))


def draw_packing(pk: Packing, path: str, title: str = "") -> None:
    """Packing layout: flap rectangles, tips, rivers, labels."""
    fig, ax = plt.subplots(figsize=(5, 5))
    for r in pk.regions:
        x0, y0, x1, y1 = r.rect
        is_river = not hasattr(r, "tip")
        face = "#cfe8cf" if is_river else "#f5f0e6"
        ax.add_patch(
            plt.Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=face,
                          edgecolor="#2ca02c", lw=2)
        )
        if not is_river:
            t = r.tip
            ax.plot([t.x0, t.x1], [t.y0, t.y1], "o-", color="#d62728",
                    ms=5, lw=2)
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, r.stick_label, ha="center",
                va="center", fontsize=8)
    G = pk.grid
    for i in range(G + 1):
        ax.plot([i, i], [0, G], color="#dddddd", lw=0.4, zorder=0)
        ax.plot([0, G], [i, i], color="#dddddd", lw=0.4, zorder=0)
    ax.set_aspect("equal")
    ax.set_xlim(-0.3, G + 0.3)
    ax.set_ylim(-0.3, G + 0.3)
    ax.set_title(title)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def draw_stick_figure(sf: StickFigure, path: str) -> None:
    """Four 3D views (Top / Side / Front / Isometric), as given to the VLM."""
    pos = sf.joint_positions(root=_root(sf))
    views = [("top", 89, -90), ("side", 0, 90), ("front", 0, 0),
             ("isometric", 25, -55)]
    fig = plt.figure(figsize=(10, 3))
    for k, (name, elev, azim) in enumerate(views):
        ax = fig.add_subplot(1, 4, k + 1, projection="3d")
        for s in sf.sticks:
            p, q = pos[s.parent], pos[s.child]
            ax.plot([p[0], q[0]], [p[1], q[1]], [p[2], q[2]], "-o",
                    color="#1f77b4", ms=3, lw=2)
        ax.view_init(elev=elev, azim=azim)
        _equal_3d(ax, np.array(list(pos.values())))
        ax.set_title(name, fontsize=9)
        ax.set_axis_off()
    fig.suptitle(sf.prompt, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def draw_folded(st: FoldedState, path: str, title: str = "",
                layer_eps: float = 0.0) -> None:
    """Seven perspectives of the folded model (paper §3.8).

    ``layer_eps`` separates coincident layers of a fully flat-folded state
    along z by BFS depth — a visualisation aid only (true layer ordering,
    the facewise CSP of Akitaya et al., is out of scope).
    """
    pts = st.vertices3d
    fig = plt.figure(figsize=(14, 6))
    for k, (name, elev, azim) in enumerate(SEVEN_VIEWS):
        ax = fig.add_subplot(2, 4, k + 1, projection="3d")
        polys = []
        for fi, face in enumerate(st.faces):
            dz = (
                layer_eps * st.face_depth[fi]
                if layer_eps and st.face_depth is not None
                else 0.0
            )
            polys.append([pts[v] + np.array([0, 0, dz]) for v in face])
        col = Poly3DCollection(polys, facecolor="#f2e8c9", edgecolor="#8a7a4e",
                               lw=0.35, alpha=0.95)
        ax.add_collection3d(col)
        ax.view_init(elev=elev, azim=azim)
        _equal_3d(ax, pts)
        ax.set_title(name, fontsize=9)
        ax.set_axis_off()
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _equal_3d(ax, pts: np.ndarray) -> None:
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    center = (lo + hi) / 2
    r = max((hi - lo).max() / 2, 1e-3)
    ax.set_xlim(center[0] - r, center[0] + r)
    ax.set_ylim(center[1] - r, center[1] + r)
    ax.set_zlim(center[2] - r, center[2] + r)


def _root(sf: StickFigure) -> int:
    children = {s.child for s in sf.sticks}
    return next(n for n in sf.nodes if n not in children)
