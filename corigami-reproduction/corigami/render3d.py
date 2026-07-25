"""Software renderer for folded models.

matplotlib's ``Poly3DCollection`` sorts faces by a crude centroid heuristic
that breaks down badly on origami: a folded base is hundreds of nearly
coplanar stacked faces, so layers punch through each other and the model
reads as noise. This module renders explicitly instead — camera transform,
per-face Lambertian shading with a two-sided paper material, and a
painter's-algorithm sort in view space — and draws the result as flat 2D
polygons, which gives exact control over occlusion order.
"""

from __future__ import annotations

import numpy as np

PAPER_FRONT = np.array([0.96, 0.91, 0.80])   # warm paper
PAPER_BACK = np.array([0.85, 0.78, 0.64])    # reverse side, slightly deeper
EDGE_COLOR = (0.35, 0.30, 0.22)


def look_at(eye: np.ndarray, target: np.ndarray, up=(0, 0, 1)) -> np.ndarray:
    """World -> camera rotation (rows = camera right/up/back axes)."""
    f = target - eye
    f = f / np.linalg.norm(f)
    up = np.asarray(up, dtype=float)
    if abs(f @ (up / np.linalg.norm(up))) > 0.999:      # degenerate up
        up = np.array([0.0, 1.0, 0.0])
    r = np.cross(f, up)
    r = r / np.linalg.norm(r)
    u = np.cross(r, f)
    return np.stack([r, u, -f])


def camera_from_angles(center: np.ndarray, radius: float,
                       elev_deg: float, azim_deg: float,
                       distance_factor: float = 3.2):
    """Eye position on a sphere around the model, matplotlib-style angles."""
    el, az = np.radians(elev_deg), np.radians(azim_deg)
    d = radius * distance_factor
    eye = center + d * np.array([
        np.cos(el) * np.cos(az),
        np.cos(el) * np.sin(az),
        np.sin(el),
    ])
    return eye


def render(ax, vertices3d: np.ndarray, faces: list[list[int]],
           elev: float, azim: float,
           light_dir=(-0.35, -0.55, 0.75),
           edges: bool = True, edge_width: float = 0.25,
           ambient: float = 0.34, rim: float = 0.10,
           margin: float = 1.06) -> None:
    """Draw a folded model into a 2D matplotlib axes with correct occlusion."""
    from matplotlib.collections import PolyCollection

    pts = np.asarray(vertices3d, dtype=float)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    center = (lo + hi) / 2
    radius = max(np.linalg.norm(hi - lo) / 2, 1e-6)

    eye = camera_from_angles(center, radius, elev, azim)
    R = look_at(eye, center)
    cam = (pts - eye) @ R.T                     # camera space; -z is forward

    # weak perspective: gentle depth cue without distorting the silhouette
    depth = -cam[:, 2]
    focal = radius * 3.2
    scale = focal / np.clip(depth, 1e-6, None)
    proj = np.stack([cam[:, 0] * scale, cam[:, 1] * scale], axis=1)

    L = np.asarray(light_dir, dtype=float)
    L = L / np.linalg.norm(L)

    polys, colors, order = [], [], []
    for face in faces:
        p3 = pts[face]
        # Newell normal (robust for near-degenerate polygons)
        n = np.zeros(3)
        for i in range(len(face)):
            a, b = p3[i], p3[(i + 1) % len(face)]
            n += np.cross(a, b)
        nn = np.linalg.norm(n)
        if nn < 1e-12:
            continue
        n /= nn

        to_eye = eye - p3.mean(axis=0)
        to_eye /= max(np.linalg.norm(to_eye), 1e-12)
        facing_front = n @ to_eye >= 0
        shade_n = n if facing_front else -n

        base = PAPER_FRONT if facing_front else PAPER_BACK
        diffuse = max(shade_n @ L, 0.0)
        # rim term lifts silhouette edges so stacked layers stay legible
        rim_term = rim * (1.0 - abs(shade_n @ to_eye))
        col = np.clip(base * (ambient + (1 - ambient) * diffuse + rim_term),
                      0, 1)

        polys.append(proj[face])
        colors.append(col)
        order.append(depth[face].mean())

    if not polys:
        return
    idx = np.argsort(order)[::-1]               # far faces first
    coll = PolyCollection(
        [polys[i] for i in idx],
        facecolors=[colors[i] for i in idx],
        edgecolors=EDGE_COLOR if edges else "none",
        linewidths=edge_width if edges else 0.0,
        antialiased=True,
    )
    ax.add_collection(coll)

    all_pts = np.concatenate(polys)
    c = (all_pts.min(axis=0) + all_pts.max(axis=0)) / 2
    r = max((all_pts.max(axis=0) - all_pts.min(axis=0)).max() / 2, 1e-6) * margin
    ax.set_xlim(c[0] - r, c[0] + r)
    ax.set_ylim(c[1] - r, c[1] + r)
    ax.set_aspect("equal")
    ax.axis("off")
