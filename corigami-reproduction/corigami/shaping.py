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

from .cp import CreasePattern
from .fold import FoldedState, fold
from .packing import FlapRegion, Packing


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
