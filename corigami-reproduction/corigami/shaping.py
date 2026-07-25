"""Minimal shaping: hinge posing (a first slice of the paper's §3.4/App. G).

The paper's tree-shaping algorithm converts the stick figure into a series
of simple folds that push the flat collapsed base into a 3D posture. The
first and most visually important of those folds is the pivot of each flap
about its base hinge. In a folded uniaxial base every flap's base boundary
maps onto a single line in folded space (the joint's axis position), so
pivoting a flap by an angle delta is an exact rigid rotation about that
line: the crease pattern is unchanged except that each base-hinge crease's
fold angle changes by +/- delta depending on the layer parity of the
neighbouring face (a rotation conjugated through an orientation-reversing
transform flips sign).

We set each crease's angle delta analytically from the flat-folded layer
parities and verify the posed state with the folding simulator's axial
strain, trying the global mirror if needed. Narrowing/clip patterns and
mid-flap simple folds (the rest of §3.5) remain out of scope.
"""

from __future__ import annotations

import math

import numpy as np

from .cp import MOUNTAIN, VALLEY, CreasePattern
from .fold import FoldedState, fold
from .packing import FlapRegion, Packing

# folding a flap much past this doubles it back over itself
MAX_POSE_DEG = 140.0


def _face_regions(cp: CreasePattern, faces: list[list[int]], pk: Packing):
    """Region index for each face, by centroid cell lookup."""
    owner = pk.cell_owner()
    out = []
    for face in faces:
        cx = sum(cp.vertices[v][0] for v in face) / len(face)
        cy = sum(cp.vertices[v][1] for v in face) / len(face)
        out.append(owner.get((int(cx), int(cy))))
    return out


def pose(cp_solved: CreasePattern, pk: Packing,
         deltas_deg: dict[str, float],
         strain_tol: float = 1e-9) -> FoldedState:
    """Pivot flaps at their base hinges by per-flap angles (degrees).

    Positive/negative rotate to opposite sides of the base plane; the
    overall mirror is resolved by trying both and keeping a valid fold.
    """
    cpp = cp_solved.planarize()
    faces = cpp.faces()
    flat = fold(cpp, planarize=False)
    if flat.mean_axial_strain > strain_tol:
        raise ValueError("base does not fold flat; cannot pose")

    face_region = _face_regions(cpp, faces, pk)
    # layer parity: z-component sign of each face's folded normal
    parity = _face_parities(cpp, faces, flat)

    # region index by stick label
    region_idx = {r.stick_label: i for i, r in enumerate(pk.regions)}

    # edge -> adjacent faces
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for fi, face in enumerate(faces):
        for a, b in zip(face, face[1:] + face[:1]):
            edge_faces.setdefault((min(a, b), max(a, b)), []).append(fi)

    def seg_key(a, b):
        p1, p2 = cpp.vertices[a], cpp.vertices[b]
        q1 = (round(p1[0] * 8) / 8, round(p1[1] * 8) / 8)
        q2 = (round(p2[0] * 8) / 8, round(p2[1] * 8) / 8)
        return (min(q1, q2), max(q1, q2))

    for mirror in (1.0, -1.0):
        overrides: dict[tuple, float] = {}
        for label, deg in deltas_deg.items():
            ri = region_idx[label]
            if not isinstance(pk.regions[ri], FlapRegion):
                raise ValueError(f"{label!r} is not a flap")
            delta = math.radians(deg) * mirror
            for (a, b), fs in edge_faces.items():
                if len(fs) != 2:
                    continue
                r1, r2 = face_region[fs[0]], face_region[fs[1]]
                if ri not in (r1, r2) or r1 == r2:
                    continue
                # neighbour (static-side) face parity sets the pulled-back
                # rotation sign
                nb = fs[1] if r1 == ri else fs[0]
                k = seg_key(a, b)
                overrides[k] = overrides.get(k, 0.0) + delta * parity[nb]
        st = fold(cpp, angle_overrides=overrides, planarize=False)
        if st.mean_axial_strain < strain_tol:
            return st
    raise ValueError(
        f"posed fold not isometric (strain {st.mean_axial_strain:.2e})"
    )


def _face_parities(cpp: CreasePattern, faces, flat: FoldedState) -> list[float]:
    pts3 = flat.vertices3d
    out = []
    for face in faces:
        n = np.zeros(3)
        for i in range(len(face)):
            n += np.cross(pts3[face[i]], pts3[face[(i + 1) % len(face)]])
        out.append(1.0 if n[2] >= 0 else -1.0)
    return out


# ---------------------------------------------------------------------------
# The simple fold (paper §3.5) and narrowing built on top of it
# ---------------------------------------------------------------------------

def _face_frames(cpp: CreasePattern, faces, flat: FoldedState):
    """Per-face rigid map CP 2D -> flat-folded 2D, as (A, t, det sign).

    The base is folded flat, so every face's folded image lies in the z=0
    plane and the map is a 2D isometry; we recover it by least squares from
    the face's own vertices.
    """
    pts2 = np.array(cpp.vertices)
    pts3 = flat.vertices3d
    out = []
    for face in faces:
        P = pts2[face]
        Q = pts3[face][:, :2]
        Pc, Qc = P - P.mean(0), Q - Q.mean(0)
        U, _, Vt = np.linalg.svd(Pc.T @ Qc)
        A = (U @ Vt).T                      # rotation or reflection
        t = Q.mean(0) - A @ P.mean(0)
        out.append((A, t, float(np.sign(np.linalg.det(A)))))
    return out


def _clip_line_to_face(poly: np.ndarray, p: np.ndarray, d: np.ndarray):
    """Segment where the infinite line (p, d) crosses a polygon, or None."""
    n = np.array([-d[1], d[0]])
    s = (poly - p) @ n
    hits = []
    for i in range(len(poly)):
        j = (i + 1) % len(poly)
        si, sj = s[i], s[j]
        if abs(si) < 1e-9:
            hits.append(poly[i])
        elif si * sj < 0:
            hits.append(poly[i] + (poly[j] - poly[i]) * (si / (si - sj)))
    if len(hits) < 2:
        return None
    ts = [float((h - p) @ d) for h in hits]
    lo, hi = int(np.argmin(ts)), int(np.argmax(ts))
    if abs(ts[hi] - ts[lo]) < 1e-9:
        return None
    return hits[lo], hits[hi]


def simple_fold(cp_solved: CreasePattern, pk: Packing,
                point, direction, mv: str = MOUNTAIN,
                labels: list[str] | None = None) -> CreasePattern:
    """Paper §3.5: fold the flat-folded base over a cut line.

    ``point``/``direction`` define the cut line in the *folded* plane. Every
    flat-folded face is intersected with that line; each intersection becomes
    a shaping crease segment on the 2D crease pattern, with its assignment
    flipped for faces whose folding path reverses orientation. ``labels``
    restricts the fold to named flaps/rivers (the paper's selective shaping).
    """
    cpp = cp_solved.planarize()
    faces = cpp.faces()
    flat = fold(cpp, planarize=False)
    frames = _face_frames(cpp, faces, flat)
    regions = _face_regions(cpp, faces, pk)
    label_of = {i: r.stick_label for i, r in enumerate(pk.regions)}

    p = np.asarray(point, dtype=float)
    d = np.asarray(direction, dtype=float)
    d = d / np.linalg.norm(d)
    other = mv if mv == MOUNTAIN else VALLEY
    flipped = VALLEY if mv == MOUNTAIN else MOUNTAIN

    out = cpp.copy()
    pts2 = np.array(cpp.vertices)
    for fi, face in enumerate(faces):
        if labels is not None:
            ri = regions[fi]
            if ri is None or label_of.get(ri) not in labels:
                continue
        A, t, det = frames[fi]
        # pull the cut line back into crease-pattern coordinates
        Ainv = np.linalg.inv(A)
        p_cp = Ainv @ (p - t)
        d_cp = Ainv @ d
        seg = _clip_line_to_face(pts2[face], p_cp, d_cp)
        if seg is None:
            continue
        out.add_crease(seg[0], seg[1], other if det > 0 else flipped)
    return out


def narrow(cp_solved: CreasePattern, pk: Packing, factor: float = 0.5,
           labels: list[str] | None = None,
           strain_tol: float = 1e-9) -> CreasePattern:
    """Narrow the folded base by simple-folding its outer edges inwards.

    Uses the base's own uniaxial geometry: the fold lines run parallel to the
    model axis, offset from the centre by ``factor`` of the current
    half-width, so the folded strip keeps its length but loses width — the
    effect the paper's narrowing templates achieve with clip patterns.
    """
    cpp = cp_solved.planarize()
    flat = fold(cpp, planarize=False)
    xy = flat.vertices3d[:, :2]

    # axis = principal direction of the flat-folded base
    centred = xy - xy.mean(0)
    _, _, Vt = np.linalg.svd(centred, full_matrices=False)
    axis = Vt[0]
    perp = np.array([-axis[1], axis[0]])

    w = centred @ perp
    lo, hi = w.min(), w.max()
    mid = (lo + hi) / 2
    half = (hi - lo) / 2
    off = half * factor
    origin = xy.mean(0)

    cp = cpp
    for sign, mv in ((+1, MOUNTAIN), (-1, VALLEY)):
        line_pt = origin + (mid + sign * off) * perp
        cp = simple_fold(cp, pk, line_pt, axis, mv, labels)
    st = fold(cp)
    if st.mean_axial_strain > strain_tol:
        raise ValueError(
            f"narrowed pattern not isometric (strain {st.mean_axial_strain:.2e})"
        )
    return cp


# ---------------------------------------------------------------------------
# Deriving pose angles from the stick figure (paper App. G, reduced)
# ---------------------------------------------------------------------------

def _flap_frames(cpp: CreasePattern, faces, flat: FoldedState, pk: Packing):
    """Per-flap (hinge axis, base point, outward direction) in folded space."""
    pts3 = flat.vertices3d
    regions = _face_regions(cpp, faces, pk)
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for fi, face in enumerate(faces):
        for a, b in zip(face, face[1:] + face[:1]):
            edge_faces.setdefault((min(a, b), max(a, b)), []).append(fi)

    out = {}
    for ri, reg in enumerate(pk.regions):
        if not isinstance(reg, FlapRegion):
            continue
        own = [fi for fi, r in enumerate(regions) if r == ri]
        if not own:
            continue
        hinge_pts = []
        for (a, b), fs in edge_faces.items():
            if len(fs) != 2:
                continue
            r1, r2 = regions[fs[0]], regions[fs[1]]
            if r1 == r2 or ri not in (r1, r2):
                continue
            hinge_pts.extend([pts3[a], pts3[b]])
        if len(hinge_pts) < 2:
            continue
        H = np.array(hinge_pts)
        base = H.mean(0)
        c = H - base
        _, _, Vt = np.linalg.svd(c, full_matrices=False)
        axis = Vt[0] / np.linalg.norm(Vt[0])
        body = np.array([pts3[v] for fi in own for v in faces[fi]])
        v0 = body.mean(0) - base
        if np.linalg.norm(v0) < 1e-9:
            continue
        out[reg.stick_label] = (axis, base, v0)
    return out


def pose_angles_from_figure(cp_solved: CreasePattern, pk: Packing,
                            sf) -> dict[str, float]:
    """Best single-hinge rotation per flap to match the stick figure.

    A flap can only rotate about its base hinge, so its reachable directions
    form a cone; we pick the angle whose resulting direction best aligns with
    the stick's 3D orientation. This is the reduced, closed-form version of
    the paper's tree-shaping constraint that a rotation be realisable as a
    simple fold on the parent's plane.
    """
    cpp = cp_solved.planarize()
    faces = cpp.faces()
    flat = fold(cpp, planarize=False)
    frames = _flap_frames(cpp, faces, flat, pk)

    out = {}
    for stick in sf.flaps:
        fr = frames.get(stick.label)
        if fr is None:
            continue
        axis, _, v0 = fr
        t = stick.direction()
        t = t / np.linalg.norm(t)
        along = (v0 @ axis) * axis
        w = v0 - along
        if np.linalg.norm(w) < 1e-9:
            continue
        cross = np.cross(axis, w)

        # Every flap hinge in a uniaxial base is parallel, so a flap can only
        # swing within one plane: a mirror-image pair is separated by sending
        # the two to opposite sides of it. Pick the side from the stick's
        # azimuth and optimise the angle within that half.
        side = math.sin(math.radians(stick.azimuth))
        if abs(side) < 0.15:                 # on the centre line: either way
            lo, hi = -MAX_POSE_DEG, MAX_POSE_DEG
        elif side > 0:
            lo, hi = 5.0, MAX_POSE_DEG
        else:
            lo, hi = -MAX_POSE_DEG, -5.0

        grid = np.linspace(lo, hi, 361)
        rad = np.radians(grid)
        v = (along[None, :]
             + np.cos(rad)[:, None] * w[None, :]
             + np.sin(rad)[:, None] * cross[None, :])
        v /= np.linalg.norm(v, axis=1, keepdims=True)
        out[stick.label] = float(grid[int(np.argmax(v @ t))])

    return _separate(out, sf)


def _separate(angles: dict[str, float], sf,
              min_gap: float = 26.0, lo: float = 22.0,
              hi: float = MAX_POSE_DEG) -> dict[str, float]:
    """Spread same-side flaps apart so coincident layers become visible.

    Matching a stick's direction alone is not enough: limbs that point along
    the base plane want a near-zero pivot, which leaves them collapsed on top
    of each other inside the base. Real shaping has to open them out, so we
    keep the stick-derived ordering and side but enforce a minimum angular
    gap between flaps sharing a side.
    """
    out = dict(angles)
    for sign in (+1, -1):
        group = [k for k, v in out.items() if (v >= 0) == (sign > 0)]
        if len(group) < 2:
            if group:
                k = group[0]
                out[k] = sign * min(max(abs(out[k]), lo), hi)
            continue
        group.sort(key=lambda k: abs(out[k]))
        span_hi = hi
        need = lo + min_gap * (len(group) - 1)
        if need > span_hi:                      # too crowded: use full span
            step = (span_hi - lo) / (len(group) - 1)
        else:
            step = max(min_gap, (span_hi - lo) / (len(group) - 1))
        for i, k in enumerate(group):
            out[k] = sign * min(lo + i * step, span_hi)
    return out
