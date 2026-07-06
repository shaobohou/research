"""Crease pattern representation (paper §2).

A crease pattern is a planar graph embedded on a square sheet of paper.
Each crease carries an assignment: Mountain, Valley, Border (paper edge),
or Unassigned (used mid-solve). Faces are extracted from the planar
subdivision and are what the folding simulator transforms rigidly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

MOUNTAIN = "M"
VALLEY = "V"
BORDER = "B"
UNASSIGNED = "U"

EPS = 1e-9


def _key(p, tol=1e-6):
    return (round(p[0] / tol) * tol, round(p[1] / tol) * tol)


@dataclass
class CreasePattern:
    """Planar graph of creases on a square [0, size] x [0, size]."""

    size: float
    vertices: list[tuple[float, float]] = field(default_factory=list)
    # edges as (i, j, assignment) with i < j vertex indices
    edges: list[tuple[int, int, str]] = field(default_factory=list)
    _vindex: dict = field(default_factory=dict, repr=False)
    _eindex: dict = field(default_factory=dict, repr=False)

    def add_vertex(self, x: float, y: float) -> int:
        k = _key((x, y))
        if k in self._vindex:
            return self._vindex[k]
        self.vertices.append((float(x), float(y)))
        idx = len(self.vertices) - 1
        self._vindex[k] = idx
        return idx

    def add_crease(self, p1, p2, assignment: str) -> None:
        i = self.add_vertex(*p1)
        j = self.add_vertex(*p2)
        if i == j:
            return
        a, b = min(i, j), max(i, j)
        if (a, b) in self._eindex:
            # keep the more specific assignment (M/V beats U/B duplicates)
            k = self._eindex[(a, b)]
            if assignment in (MOUNTAIN, VALLEY):
                self.edges[k] = (a, b, assignment)
            return
        self.edges.append((a, b, assignment))
        self._eindex[(a, b)] = len(self.edges) - 1

    def set_assignment(self, i: int, j: int, assignment: str) -> None:
        a, b = min(i, j), max(i, j)
        k = self._eindex[(a, b)]
        self.edges[k] = (a, b, assignment)

    def assignment(self, i: int, j: int) -> str:
        a, b = min(i, j), max(i, j)
        return self.edges[self._eindex[(a, b)]][2]

    # ---------------------------------------------------------------- utils

    def is_border_vertex(self, i: int, tol: float = 1e-6) -> bool:
        x, y = self.vertices[i]
        return (
            abs(x) < tol
            or abs(y) < tol
            or abs(x - self.size) < tol
            or abs(y - self.size) < tol
        )

    def neighbors(self, i: int) -> list[tuple[int, str]]:
        out = []
        for a, b, asg in self.edges:
            if a == i:
                out.append((b, asg))
            elif b == i:
                out.append((a, asg))
        return out

    def planarize(self) -> "CreasePattern":
        """Split all crossing / overlapping creases at intersection points.

        Solver stages emit creases independently, so segments may cross or
        share interior points; faces and vertex checks need a proper planar
        subdivision.
        """
        segs = [
            (np.array(self.vertices[a]), np.array(self.vertices[b]), asg)
            for a, b, asg in self.edges
        ]
        cut_points: list[list[np.ndarray]] = [[] for _ in segs]
        for i in range(len(segs)):
            p1, p2, _ = segs[i]
            for j in range(i + 1, len(segs)):
                q1, q2, _ = segs[j]
                for pt in _seg_intersections(p1, p2, q1, q2):
                    cut_points[i].append(pt)
                    cut_points[j].append(pt)
        out = CreasePattern(self.size)
        for (p1, p2, asg), cuts in zip(segs, cut_points):
            d = p2 - p1
            L = np.linalg.norm(d)
            ts = sorted({0.0, 1.0} | {
                float(np.dot(c - p1, d) / (L * L)) for c in cuts
            })
            ts = [t for t in ts if -EPS < t < 1 + EPS]
            for t0, t1 in zip(ts, ts[1:]):
                if t1 - t0 < 1e-9:
                    continue
                out.add_crease(p1 + t0 * d, p1 + t1 * d, asg)
        return out

    def faces(self) -> list[list[int]]:
        """Extract faces of the planar subdivision (CCW interior faces).

        Standard half-edge trace: at each vertex, outgoing half-edges are
        sorted by angle; the "next" half-edge after arriving over (u, v) is
        the one after the reverse direction in clockwise order, which walks
        each face with the interior on the left. The single clockwise outer
        face (most-negative signed area) is dropped.
        """
        pts = [np.array(v) for v in self.vertices]
        adj: dict[int, list[int]] = {}
        for a, b, _ in self.edges:
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
        angle_of = {}
        for u, vs in adj.items():
            vs.sort(key=lambda v: math.atan2(*(pts[v] - pts[u])[::-1]))
            for v in vs:
                angle_of[(u, v)] = math.atan2(*(pts[v] - pts[u])[::-1])

        visited: set[tuple[int, int]] = set()
        faces = []
        for a, b, _ in self.edges:
            for he in ((a, b), (b, a)):
                if he in visited:
                    continue
                face = []
                u, v = he
                while (u, v) not in visited:
                    visited.add((u, v))
                    face.append(u)
                    # candidates out of v, pick the one just CW of (v -> u)
                    outs = adj[v]
                    back = angle_of[(v, u)]
                    best = min(
                        (w for w in outs if w != u or len(outs) == 1),
                        key=lambda w: (back - angle_of[(v, w)]) % (2 * math.pi)
                        or 2 * math.pi,
                    )
                    u, v = v, best
                area = _signed_area([pts[i] for i in face])
                if area > EPS:
                    faces.append(face)
        return faces

    def copy(self) -> "CreasePattern":
        cp = CreasePattern(self.size)
        cp.vertices = list(self.vertices)
        cp.edges = list(self.edges)
        cp._vindex = dict(self._vindex)
        cp._eindex = dict(self._eindex)
        return cp


def _signed_area(poly) -> float:
    s = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def _seg_intersections(p1, p2, q1, q2):
    """Intersection points of two segments, incl. T-junctions and overlaps."""
    d1, d2 = p2 - p1, q2 - q1
    denom = d1[0] * d2[1] - d1[1] * d2[0]
    pts = []
    if abs(denom) > EPS:
        t = ((q1 - p1)[0] * d2[1] - (q1 - p1)[1] * d2[0]) / denom
        s = ((q1 - p1)[0] * d1[1] - (q1 - p1)[1] * d1[0]) / denom
        if -EPS <= t <= 1 + EPS and -EPS <= s <= 1 + EPS:
            pts.append(p1 + t * d1)
    else:
        # parallel: collect endpoints lying on the other segment (overlap)
        for pt in (q1, q2):
            if _on_segment(pt, p1, p2):
                pts.append(pt)
        for pt in (p1, p2):
            if _on_segment(pt, q1, q2):
                pts.append(pt)
    return pts


def _on_segment(pt, a, b, tol=1e-9) -> bool:
    d = b - a
    L2 = float(d @ d)
    if L2 < tol:
        return False
    cross = (pt - a)[0] * d[1] - (pt - a)[1] * d[0]
    if abs(cross) > 1e-7 * math.sqrt(L2):
        return False
    t = float((pt - a) @ d) / L2
    return -tol <= t <= 1 + tol
