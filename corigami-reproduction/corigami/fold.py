"""Deterministic geometric folding simulator (paper §3.7, Appendix H).

Constructs the 3D geometry of the folded model directly from the 2D crease
pattern: parse into vertices/edges/faces, build the face-adjacency graph
(faces adjacent iff they share an edge), BFS from an arbitrary root face,
and give each face a global 4x4 affine transform. A child's transform is the
parent's composed with a rotation about the shared crease line by the crease
fold angle (translate edge to origin, rotate about the edge axis, translate
back). Vertex positions are averaged over all incident faces, and geometric
consistency is measured by the mean axial strain (relative edge-length
change between the 2D and folded 3D states).
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

import numpy as np

from .cp import BORDER, MOUNTAIN, UNASSIGNED, VALLEY, CreasePattern

# Flat fold: +/- pi. Faces are traced CCW so a child face lies to the right
# of the shared oriented edge; rotating +pi about that axis sends it below
# the parent plane (mountain), -pi above (valley).
FOLD_ANGLES = {MOUNTAIN: math.pi, VALLEY: -math.pi, BORDER: 0.0, UNASSIGNED: 0.0}


@dataclass
class FoldedState:
    vertices3d: np.ndarray            # (n, 3) folded vertex coordinates
    faces: list[list[int]]            # vertex-index loops
    mean_axial_strain: float
    max_axial_strain: float
    face_depth: list[int] | None = None   # BFS depth per face (layer hint)


def _rot_about_line(p: np.ndarray, d: np.ndarray, angle: float) -> np.ndarray:
    """4x4 transform: rotation by ``angle`` about the 3D line through p along d."""
    d = d / np.linalg.norm(d)
    x, y, z = d
    c, s, C = math.cos(angle), math.sin(angle), 1 - math.cos(angle)
    R = np.array(
        [
            [x * x * C + c, x * y * C - z * s, x * z * C + y * s],
            [y * x * C + z * s, y * y * C + c, y * z * C - x * s],
            [z * x * C - y * s, z * y * C + x * s, z * z * C + c],
        ]
    )
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = p - R @ p
    return T


def fold(cp: CreasePattern, fold_fraction: float = 1.0) -> FoldedState:
    """Fold a crease pattern; ``fold_fraction`` scales all fold angles (1 = flat)."""
    cp = cp.planarize()
    faces = cp.faces()
    if not faces:
        raise ValueError("crease pattern has no faces")
    pts2 = np.array(cp.vertices)

    # face adjacency via shared undirected edges
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for fi, face in enumerate(faces):
        for a, b in zip(face, face[1:] + face[:1]):
            edge_faces.setdefault((min(a, b), max(a, b)), []).append(fi)

    assignment = {(min(a, b), max(a, b)): asg for a, b, asg in cp.edges}

    transforms: list[np.ndarray | None] = [None] * len(faces)
    transforms[0] = np.eye(4)
    depth: list[int] = [0] * len(faces)
    q = deque([0])
    while q:
        fi = q.popleft()
        for a, b in zip(faces[fi], faces[fi][1:] + faces[fi][:1]):
            e = (min(a, b), max(a, b))
            for fj in edge_faces.get(e, []):
                if fj == fi or transforms[fj] is not None:
                    continue
                asg = assignment.get(e, UNASSIGNED)
                angle = FOLD_ANGLES[asg] * fold_fraction
                # rotation direction depends on which side the child face
                # lies: traverse the shared edge as oriented in the parent
                # face so the child is on its right; folding is then a
                # rotation about that oriented axis.
                p = np.array([*pts2[a], 0.0])
                d = np.array([*(pts2[b] - pts2[a]), 0.0])
                local = _rot_about_line(p, d, angle)
                transforms[fj] = transforms[fi] @ local
                depth[fj] = depth[fi] + 1
                q.append(fj)

    if any(t is None for t in transforms):
        # disconnected faces (shouldn't happen on valid patterns): keep flat
        transforms = [np.eye(4) if t is None else t for t in transforms]

    # resolve vertices by averaging across incident faces
    acc = np.zeros((len(pts2), 3))
    cnt = np.zeros(len(pts2))
    for fi, face in enumerate(faces):
        T = transforms[fi]
        for v in face:
            hom = T @ np.array([pts2[v][0], pts2[v][1], 0.0, 1.0])
            acc[v] += hom[:3]
            cnt[v] += 1
    cnt[cnt == 0] = 1
    pts3 = acc / cnt[:, None]

    # mean axial strain: relative edge-length change
    strains = []
    for a, b, _ in cp.edges:
        l2 = np.linalg.norm(pts2[a] - pts2[b])
        l3 = np.linalg.norm(pts3[a] - pts3[b])
        if l2 > 1e-12:
            strains.append(abs(l3 - l2) / l2)
    return FoldedState(
        vertices3d=pts3,
        faces=faces,
        mean_axial_strain=float(np.mean(strains)),
        max_axial_strain=float(np.max(strains)),
        face_depth=depth,
    )
