"""Crease construction + Mountain/Valley solving (paper §3.3, Appendix F).

Stage 1 (deterministic, App. F.1): from a valid packing, construct
 - hinge creases: internal region boundaries,
 - ridge creases: the L-infinity straight skeleton of each flap ball
   (45-degree diagonals from tip endpoints, plus the tip segment),
 - axial pleats: integer grid edges parallel to the local elevation
   gradient (the paper builds these by filtering a dense orthogonal grid;
   our elevation model gives the surviving segments directly).

Stage 2 (combinatorial, App. F.2/F.3): assign M/V to every crease. The
paper uses deterministic pleat interleaving + ridge propagation, then a
priority-driven greedy search over hinge assignments scored by local
flat-foldability. We implement the same search problem as a backtracking
CSP over crease assignments with per-vertex Kawasaki/Maekawa/crimp pruning
(complete at our scale, greedy-first by most-constrained-vertex ordering).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .cp import BORDER, MOUNTAIN, UNASSIGNED, VALLEY, CreasePattern
from .foldability import crimp_foldable, kawasaki, maekawa
from .packing import FlapRegion, Packing, RiverRegion

RIDGE, HINGE, PLEAT = "ridge", "hinge", "pleat"


class SolveError(Exception):
    pass


# --------------------------------------------------------------------------
# Stage 1: crease construction
# --------------------------------------------------------------------------

def build_crease_pattern(pk: Packing) -> tuple[CreasePattern, dict]:
    """Unassigned crease pattern from a packing; returns (cp, kind-by-segment)."""
    G = pk.grid
    cp = CreasePattern(float(G))
    kinds: dict[tuple, str] = {}

    def seg_key(p1, p2):
        a = (round(p1[0] * 4) / 4, round(p1[1] * 4) / 4)
        b = (round(p2[0] * 4) / 4, round(p2[1] * 4) / 4)
        return (min(a, b), max(a, b))

    def add(p1, p2, kind, assignment=UNASSIGNED):
        cp.add_crease(p1, p2, assignment)
        kinds[seg_key(p1, p2)] = kind

    # paper border
    for p1, p2 in [((0, 0), (G, 0)), ((G, 0), (G, G)), ((G, G), (0, G)),
                   ((0, G), (0, 0))]:
        cp.add_crease(p1, p2, BORDER)

    owner = pk.cell_owner()

    # ridges + tip segments
    tip_edges = set()
    for r in pk.regions:
        if not isinstance(r, FlapRegion):
            continue
        t = r.tip
        ends = [(t.x0, t.y0), (t.x1, t.y1)]
        if t.is_point:
            dirs = [[(-1, -1), (-1, 1), (1, -1), (1, 1)]] * 1
            end_dirs = [(ends[0], d) for d in dirs[0]]
        elif t.y0 == t.y1:  # horizontal tip
            end_dirs = [(ends[0], (-1, -1)), (ends[0], (-1, 1)),
                        (ends[1], (1, -1)), (ends[1], (1, 1))]
        else:               # vertical tip
            end_dirs = [(ends[0], (-1, -1)), (ends[0], (1, -1)),
                        (ends[1], (-1, 1)), (ends[1], (1, 1))]
        for (ex, ey), (dx, dy) in end_dirs:
            # clip diagonal of length l to the paper square
            reach = r.length
            if dx < 0:
                reach = min(reach, ex)
            else:
                reach = min(reach, G - ex)
            if dy < 0:
                reach = min(reach, ey)
            else:
                reach = min(reach, G - ey)
            if reach > 0:
                add((ex, ey), (ex + dx * reach, ey + dy * reach), RIDGE)
        if not t.is_point:
            add((t.x0, t.y0), (t.x1, t.y1), RIDGE)
            # remember unit edges covered by the tip segment
            if t.y0 == t.y1:
                for x in range(t.x0, t.x1):
                    tip_edges.add((("h"), x, t.y0))
            else:
                for y in range(t.y0, t.y1):
                    tip_edges.add((("v"), t.x0, y))

    # hinges and pleats on unit grid edges
    for i in range(0, G + 1):
        for j in range(0, G):
            # vertical unit edge x=i, y in [j, j+1]
            if i in (0, G):
                continue  # border already added
            left, right = owner.get((i - 1, j)), owner.get((i, j))
            if left is None or right is None:
                raise SolveError("packing does not tile the grid")
            if left != right:
                add((i, j), (i, j + 1), HINGE)
            elif ("v", i, j) not in tip_edges:
                reg = pk.regions[left]
                if (reg.grad_axis(i - 0.25, j + 0.5) == "y"
                        and reg.grad_axis(i + 0.25, j + 0.5) == "y"):
                    add((i, j), (i, j + 1), PLEAT)
    for j in range(0, G + 1):
        for i in range(0, G):
            # horizontal unit edge y=j, x in [i, i+1]
            if j in (0, G):
                continue
            below, above = owner.get((i, j - 1)), owner.get((i, j))
            if below != above:
                add((i, j), (i + 1, j), HINGE)
            elif ("h", i, j) not in tip_edges:
                reg = pk.regions[below]
                if (reg.grad_axis(i + 0.5, j - 0.25) == "x"
                        and reg.grad_axis(i + 0.5, j + 0.25) == "x"):
                    add((i, j), (i + 1, j), PLEAT)

    return cp, kinds


# --------------------------------------------------------------------------
# Stage 2: M/V assignment as backtracking search with local pruning
# --------------------------------------------------------------------------

@dataclass
class _Vertex:
    angles: list[float]        # sector angles between CCW-consecutive creases
    edge_ids: list[int]        # incident crease ids in CCW order
    interior: bool


def _vertex_data(cp: CreasePattern) -> list[_Vertex]:
    pts = np.array(cp.vertices)
    incident: dict[int, list[int]] = {}
    for eid, (a, b, _) in enumerate(cp.edges):
        incident.setdefault(a, []).append(eid)
        incident.setdefault(b, []).append(eid)
    out = []
    for v in range(len(cp.vertices)):
        eids = incident.get(v, [])
        items = []
        for eid in eids:
            a, b, _ = cp.edges[eid]
            u = b if a == v else a
            d = pts[u] - pts[v]
            items.append((math.atan2(d[1], d[0]) % (2 * math.pi), eid))
        items.sort()
        dirs = [t for t, _ in items]
        n = len(items)
        angles = [
            (dirs[(k + 1) % n] - dirs[k]) % (2 * math.pi) for k in range(n)
        ]
        out.append(
            _Vertex(
                angles=angles,
                edge_ids=[eid for _, eid in items],
                interior=not cp.is_border_vertex(v),
            )
        )
    return out


def _vertex_feasible(vx: _Vertex, assignment: list[str]) -> bool:
    """Local feasibility of a (possibly partial) vertex assignment."""
    asgs = [assignment[eid] for eid in vx.edge_ids]
    unassigned = [k for k, a in enumerate(asgs) if a == UNASSIGNED]
    if not unassigned:
        return maekawa(asgs) and crimp_foldable(vx.angles, asgs)
    m = asgs.count(MOUNTAIN)
    v = asgs.count(VALLEY)
    u = len(unassigned)
    if abs(m - v) > u + 2:
        return False
    if u <= 4:
        # enumerate completions
        for bits in range(1 << u):
            trial = list(asgs)
            for k, idx in enumerate(unassigned):
                trial[idx] = MOUNTAIN if (bits >> k) & 1 else VALLEY
            if maekawa(trial) and crimp_foldable(vx.angles, trial):
                return True
        return False
    return True


def assign_mv(cp: CreasePattern, max_nodes: int = 200_000) -> CreasePattern | None:
    """Backtracking search for a locally flat-foldable M/V assignment."""
    verts = _vertex_data(cp)

    # Kawasaki is assignment-independent: check it up-front.
    for vx in verts:
        if vx.interior and not kawasaki(vx.angles):
            raise SolveError(
                f"Kawasaki violated at a vertex (angles="
                f"{[round(math.degrees(a), 1) for a in vx.angles]}); "
                "crease construction is inconsistent"
            )

    assignment = [asg for _, _, asg in cp.edges]
    edge_verts: dict[int, list[int]] = {}
    for vid, vx in enumerate(verts):
        for eid in vx.edge_ids:
            edge_verts.setdefault(eid, []).append(vid)

    unassigned = {eid for eid, a in enumerate(assignment) if a == UNASSIGNED}
    nodes = 0

    def vertex_slack(vid: int) -> int:
        return sum(
            1 for eid in verts[vid].edge_ids if assignment[eid] == UNASSIGNED
        )

    def choose() -> int:
        # most-constrained: crease at the interior vertex with fewest
        # unassigned incident creases (the paper's priority-driven ordering)
        best, best_key = None, None
        for eid in unassigned:
            for vid in edge_verts[eid]:
                if not verts[vid].interior:
                    continue
                key = (vertex_slack(vid), -len(verts[vid].edge_ids))
                if best_key is None or key < best_key:
                    best, best_key = eid, key
        return best if best is not None else next(iter(unassigned))

    def consistent(eid: int) -> bool:
        return all(
            not verts[vid].interior
            or _vertex_feasible(verts[vid], assignment)
            for vid in edge_verts[eid]
        )

    def dfs() -> bool:
        nonlocal nodes
        if not unassigned:
            return True
        nodes += 1
        if nodes > max_nodes:
            return False
        eid = choose()
        unassigned.discard(eid)
        for val in (MOUNTAIN, VALLEY):
            assignment[eid] = val
            if consistent(eid) and dfs():
                return True
        assignment[eid] = UNASSIGNED
        unassigned.add(eid)
        return False

    if not dfs():
        return None
    solved = cp.copy()
    for eid, val in enumerate(assignment):
        a, b, _ = solved.edges[eid]
        solved.edges[eid] = (a, b, val)
    return solved
