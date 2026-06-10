"""Origami model container: triangulated mesh + crease/beam constraint data.

Mirrors the data the original OrigamiSimulator (MIT, amandaghassaei/OrigamiSimulator)
feeds its GPU solver. Can be built from:
  - model.json exported from the running original app (extract_groundtruth.js), or
  - a FOLD file with triangular faces (loads + triangulates quads by fan split,
    centers and scales like model.js sync()).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

import numpy as np


@dataclass
class OrigamiModel:
    pos0: np.ndarray  # (N,3) float32, original (centered+scaled) positions
    fixed: np.ndarray  # (N,) bool
    mass: np.ndarray  # (N,) float32
    edges: np.ndarray  # (E,2) int32
    edge_k: np.ndarray  # (E,) float32   axialStiffness / restLength
    edge_d: np.ndarray  # (E,) float32   damping coefficient
    edge_l0: np.ndarray  # (E,) float32   rest length
    faces: np.ndarray  # (F,3) int32
    nominal_angles: np.ndarray  # (F,3) float32  triangle angles at rest
    # creases: per fold/facet edge with two adjacent faces
    crease_faces: np.ndarray  # (C,2) int32  [face1, face2]
    crease_nodes: np.ndarray  # (C,4) int32  [node1(opp f1), node2(opp f2), edge n3, edge n4]
    crease_k: np.ndarray  # (C,) float32
    crease_target: np.ndarray  # (C,) float32  target fold angle (radians)
    dt: float
    # edge index lists per FOLD assignment, for line rendering
    lines: dict[str, np.ndarray]

    @property
    def num_nodes(self) -> int:
        return self.pos0.shape[0]


def _nominal_angles(pos: np.ndarray, faces: np.ndarray) -> np.ndarray:
    a, b, c = pos[faces[:, 0]], pos[faces[:, 1]], pos[faces[:, 2]]

    def unit(v):
        return v / np.linalg.norm(v, axis=-1, keepdims=True)

    ab, ac, bc = unit(b - a), unit(c - a), unit(c - b)

    def dot(u, v):
        return np.clip(np.sum(u * v, axis=-1), -1.0, 1.0)

    return np.stack(
        [np.arccos(dot(ab, ac)), np.arccos(-dot(ab, bc)), np.arccos(dot(ac, bc))],
        axis=-1,
    ).astype(np.float32)


def _calc_dt(edge_k: np.ndarray, mass_min: float = 1.0) -> float:
    max_freq = float(np.max(np.sqrt(edge_k / mass_min)))
    return (1.0 / (2.0 * math.pi * max_freq)) * 0.9


def load_model_json(path: str) -> tuple[OrigamiModel, dict]:
    """Load a model exported from the original app; returns (model, raw params)."""
    with open(path) as f:
        d = json.load(f)
    pos0 = np.asarray(d["positions"], dtype=np.float32)
    edges = np.asarray(d["edges"], dtype=np.int32)
    faces = np.asarray(d["faces"], dtype=np.int32)
    creases = d["creases"]

    lines: dict[str, list[int]] = {k: [] for k in "MVBFUC"}
    for ev, assign in zip(d["edgesVerticesFold"], d["edgesAssignment"]):
        lines[assign].extend(ev)

    model = OrigamiModel(
        pos0=pos0,
        fixed=np.asarray(d["fixed"], dtype=bool),
        mass=np.ones(len(pos0), dtype=np.float32),
        edges=edges,
        edge_k=np.asarray(d["edgeK"], dtype=np.float32),
        edge_d=np.asarray(d["edgeD"], dtype=np.float32),
        edge_l0=np.asarray(d["edgeLength"], dtype=np.float32),
        faces=faces,
        nominal_angles=_nominal_angles(pos0, faces),
        crease_faces=np.asarray([[c["face1"], c["face2"]] for c in creases], dtype=np.int32),
        crease_nodes=np.asarray(
            [[c["node1"], c["node2"], c["edge"][0], c["edge"][1]] for c in creases],
            dtype=np.int32,
        ),
        crease_k=np.asarray([c["k"] for c in creases], dtype=np.float32),
        crease_target=np.asarray([c["targetTheta"] for c in creases], dtype=np.float32),
        dt=0.0,
        lines={k: np.asarray(v, dtype=np.int32).reshape(-1, 2) for k, v in lines.items()},
    )
    model.dt = _calc_dt(model.edge_k)
    return model, d["params"]


def load_fold(
    fold_or_path: str | dict,
    axial_stiffness: float = 20.0,
    crease_stiffness: float = 0.7,
    panel_stiffness: float = 0.7,
    percent_damping: float = 0.45,
) -> OrigamiModel:
    """Standalone FOLD loader replicating the original's preprocessing
    (pattern.js processFold + model.js sync) for FOLD data that already carries
    edges_foldAngle. Accepts a file path or a FOLD dict (e.g. from
    origami.svg_import.svg_to_fold). Polygon faces are fan-triangulated;
    new facet edges get assignment "F" with fold angle 0, like
    triangulatePolys()."""
    if isinstance(fold_or_path, dict):
        fold = fold_or_path
    else:
        with open(fold_or_path) as f:
            fold = json.load(f)

    verts = [v if len(v) == 3 else [v[0], 0.0, v[1]] for v in fold["vertices_coords"]]
    pos = np.asarray(verts, dtype=np.float64)
    edges_vertices = [list(e) for e in fold["edges_vertices"]]
    assignments = list(fold["edges_assignment"])
    fold_angles = list(fold.get("edges_foldAngle", [None] * len(edges_vertices)))

    # triangulate polygon faces, adding "F" facet edges.
    # quads split along the shorter diagonal like the original triangulatePolys();
    # larger polygons (which the original handles with earcut) are fan-triangulated.
    tri_faces: list[list[int]] = []
    for face in fold["faces_vertices"]:
        face = list(face)
        if len(face) == 3:
            tri_faces.append(face)
            continue
        if len(face) == 4:
            d1 = np.sum((pos[face[0]] - pos[face[2]]) ** 2)
            d2 = np.sum((pos[face[1]] - pos[face[3]]) ** 2)
            if d2 < d1:
                edges_vertices.append([face[1], face[3]])
                tri_faces.append([face[0], face[1], face[3]])
                tri_faces.append([face[1], face[2], face[3]])
            else:
                edges_vertices.append([face[0], face[2]])
                tri_faces.append([face[0], face[1], face[2]])
                tri_faces.append([face[0], face[2], face[3]])
            assignments.append("F")
            fold_angles.append(0.0)
            continue
        for i in range(1, len(face) - 1):
            tri_faces.append([face[0], face[i], face[i + 1]])
            if i < len(face) - 2:
                edges_vertices.append([face[0], face[i + 1]])
                assignments.append("F")
                fold_angles.append(0.0)
    faces = np.asarray(tri_faces, dtype=np.int32)
    edges = np.asarray(edges_vertices, dtype=np.int32)

    # center on bounding-box center, scale by 1/boundingSphere.radius (three.js style)
    center = (pos.max(axis=0) + pos.min(axis=0)) / 2.0
    pos -= center
    pos /= np.max(np.linalg.norm(pos, axis=1))
    pos0 = pos.astype(np.float32)

    # crease params: for each M/V/F edge find the two adjacent faces and the
    # opposite vertices; face1 = face where the edge runs v1->v2 *with* the winding
    # (matches pattern.js getFacesAndVerticesForEdges)
    face_sets = [set(f) for f in tri_faces]
    crease_faces, crease_nodes, crease_k, crease_target = [], [], [], []
    for ei, (ev, assign, ang) in enumerate(zip(edges_vertices, assignments, fold_angles)):
        if assign not in ("M", "V", "F") or ang is None:
            continue
        v1, v2 = ev
        adj = []
        for fi, fs in enumerate(face_sets):
            if v1 in fs and v2 in fs:
                face = tri_faces[fi]
                opp = (fs - {v1, v2}).pop()
                # edge in forward winding order in this face?
                i1 = face.index(v1)
                forward = face[(i1 + 1) % 3] == v2
                adj.append((fi, opp, forward))
                if len(adj) == 2:
                    break
        if len(adj) < 2:
            continue
        (fa, oa, fwd_a), (fb, ob, _) = adj
        if not fwd_a:
            (fa, oa), (fb, ob) = (fb, ob), (fa, oa)
        length = float(np.linalg.norm(pos0[v2] - pos0[v1]))
        k = (crease_stiffness if ang != 0 else panel_stiffness) * length
        crease_faces.append([fa, fb])
        crease_nodes.append([oa, ob, v1, v2])
        crease_k.append(k)
        crease_target.append(math.radians(ang))

    edge_vec = pos0[edges[:, 1]] - pos0[edges[:, 0]]
    edge_l0 = np.linalg.norm(edge_vec, axis=1).astype(np.float32)
    edge_k = (axial_stiffness / edge_l0).astype(np.float32)
    edge_d = (percent_damping * 2.0 * np.sqrt(edge_k)).astype(np.float32)  # mass = 1

    lines: dict[str, list[int]] = {k: [] for k in "MVBFUC"}
    for ev, assign in zip(edges_vertices, assignments):
        lines[assign].extend(ev)

    model = OrigamiModel(
        pos0=pos0,
        fixed=np.zeros(len(pos0), dtype=bool),
        mass=np.ones(len(pos0), dtype=np.float32),
        edges=edges,
        edge_k=edge_k,
        edge_d=edge_d,
        edge_l0=edge_l0,
        faces=faces,
        nominal_angles=_nominal_angles(pos0, faces),
        crease_faces=np.asarray(crease_faces, dtype=np.int32),
        crease_nodes=np.asarray(crease_nodes, dtype=np.int32),
        crease_k=np.asarray(crease_k, dtype=np.float32),
        crease_target=np.asarray(crease_target, dtype=np.float32),
        dt=_calc_dt(edge_k),
        lines={k: np.asarray(v, dtype=np.int32).reshape(-1, 2) for k, v in lines.items()},
    )
    return model
