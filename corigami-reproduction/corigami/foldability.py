"""Local flat-foldability checks (paper §2, Appendix D, Algorithm 1).

Kawasaki's theorem: alternating sums of consecutive sector angles at an
interior vertex each equal 180 degrees.
Maekawa's theorem: |#Mountain - #Valley| = 2 at an interior vertex.
These are necessary but not sufficient once M/V assignments are considered;
the sufficient local test is the crimping algorithm (a generalisation of the
Big-Little-Big lemma), reproduced from the paper's Algorithm 1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .cp import BORDER, MOUNTAIN, UNASSIGNED, VALLEY, CreasePattern

ANG_TOL = 1e-6


@dataclass
class VertexReport:
    vertex: int
    interior: bool
    kawasaki: bool
    maekawa: bool
    crimp: bool

    @property
    def flat_foldable(self) -> bool:
        return not self.interior or (self.kawasaki and self.maekawa and self.crimp)


def sector_angles(directions: list[float]) -> list[float]:
    """Sector angles between consecutive creases sorted CCW around a vertex."""
    ds = sorted(d % (2 * math.pi) for d in directions)
    return [
        (ds[(i + 1) % len(ds)] - ds[i]) % (2 * math.pi) for i in range(len(ds))
    ]


def kawasaki(angles: list[float], tol: float = ANG_TOL) -> bool:
    if len(angles) % 2 != 0:
        return False
    alt = sum(a * (1 if i % 2 == 0 else -1) for i, a in enumerate(angles))
    return abs(alt) < tol


def maekawa(assignments: list[str]) -> bool:
    m = assignments.count(MOUNTAIN)
    v = assignments.count(VALLEY)
    return abs(m - v) == 2 and m + v == len(assignments)


class _Sector:
    __slots__ = ("theta", "left", "right", "prev", "next")

    def __init__(self, theta: float, left: str, right: str):
        self.theta = theta
        self.left = left     # bounding crease CCW-before the sector
        self.right = right   # bounding crease CCW-after the sector
        self.prev: "_Sector" | None = None
        self.next: "_Sector" | None = None


def crimp_foldable(angles: list[float], assignments: list[str]) -> bool:
    """Paper Algorithm 1: sufficient local flat-foldability via crimping.

    ``angles[i]`` is the sector between crease i and crease i+1 (circularly);
    ``assignments[i]`` is the M/V label of crease i. Iteratively finds a
    non-strict local-minimum sector whose bounding creases differ (one M,
    one V), crimps it away, and accepts iff the final two sectors are bounded
    by identical assignments.
    """
    n = len(angles)
    if n != len(assignments) or n < 2:
        return False
    if not maekawa(assignments):
        return False

    sectors = [
        _Sector(angles[i], assignments[i], assignments[(i + 1) % n])
        for i in range(n)
    ]
    for i, s in enumerate(sectors):
        s.prev = sectors[(i - 1) % n]
        s.next = sectors[(i + 1) % n]
    active = set(sectors)

    def is_local_min(s: _Sector) -> bool:
        if s.left == s.right:
            return False
        return s.theta <= s.prev.theta + ANG_TOL and s.theta <= s.next.theta + ANG_TOL

    queue = {s for s in active if is_local_min(s)}
    while queue and len(active) > 2:
        s = queue.pop()
        if s not in active or not is_local_min(s):
            continue
        L, R = s.prev, s.next
        if L is s or R is s or L is R:
            break
        L.theta = L.theta - s.theta + R.theta   # simulate the crimp
        L.right = R.right                        # merge bounding creases
        # unlink s and R
        L.next = R.next
        R.next.prev = L
        active.discard(s)
        active.discard(R)
        queue.discard(R)
        for x in (L.prev, L, L.next):
            if x in active and is_local_min(x):
                queue.add(x)

    if len(active) == 2:
        rem = list(active)
        creases = {rem[0].left, rem[0].right, rem[1].left, rem[1].right}
        return len(creases) == 1
    return False


def check_vertex(cp: CreasePattern, v: int) -> VertexReport:
    pts = np.array(cp.vertices)
    nbrs = cp.neighbors(v)
    interior = not cp.is_border_vertex(v)
    if not interior:
        return VertexReport(v, False, True, True, True)

    # order creases CCW by angle
    items = []
    for u, asg in nbrs:
        d = pts[u] - pts[v]
        items.append((math.atan2(d[1], d[0]) % (2 * math.pi), asg))
    items.sort()
    dirs = [a for a, _ in items]
    asgs = [asg for _, asg in items]
    n = len(items)
    angles = [(dirs[(i + 1) % n] - dirs[i]) % (2 * math.pi) for i in range(n)]

    if any(a == UNASSIGNED for a in asgs):
        return VertexReport(v, True, kawasaki(angles), False, False)
    return VertexReport(
        v,
        True,
        kawasaki(angles),
        maekawa(asgs),
        crimp_foldable(angles, asgs),
    )


def check_pattern(cp: CreasePattern) -> tuple[bool, list[VertexReport]]:
    """Check every interior vertex; pattern-level local flat-foldability."""
    reports = [check_vertex(cp, v) for v in range(len(cp.vertices))]
    return all(r.flat_foldable for r in reports), reports
