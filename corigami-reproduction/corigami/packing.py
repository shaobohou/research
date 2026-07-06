"""Discrete rectangle packing of a stick figure onto the grid (paper §3.2, App. E).

Uniaxial box pleating, elevation-function formulation:

- A flap (leaf stick, length ``l``, base joint ``u``) occupies the L-infinity
  ball of radius ``l`` around an axis-aligned integer *tip segment* (possibly
  a point), clipped only by the paper border. Elevation inside is
  ``pos(u) + l - d_inf(p, tip)``; every non-border boundary point is at
  distance exactly ``l``, i.e. constant elevation ``pos(u)`` — internal
  boundaries are hinge-consistent by construction. A stretched tip segment
  is the paper's "flap expansion" used to eliminate tiling gaps.
- A river (internal stick, length ``k``) occupies a straight full-span strip
  of width ``k``; elevation varies linearly between its two walls.

A valid packing tiles the grid exactly and every internal boundary separates
regions that agree on the tree node at that elevation (flap-flap: same base
joint; flap-river: the river wall at the flap's joint). The packer is a
backtracking search over river placement and flap tip placements, mirroring
the paper's river-first traversal with immediate pocket packing.

Scope restrictions vs. the paper (documented in README): at most one river,
straight (no L-shapes / wall-following), and each pocket's flaps must share
a single joint (star pockets).
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass

from .stickfigure import Stick, StickFigure


@dataclass(frozen=True)
class Tip:
    """Axis-aligned integer segment (possibly degenerate)."""

    x0: int
    y0: int
    x1: int
    y1: int

    def dist(self, x: float, y: float) -> float:
        dx = max(0.0, self.x0 - x, x - self.x1)
        dy = max(0.0, self.y0 - y, y - self.y1)
        return max(dx, dy)

    @property
    def is_point(self) -> bool:
        return self.x0 == self.x1 and self.y0 == self.y1


@dataclass(frozen=True)
class FlapRegion:
    stick_label: str
    joint: int              # tree node at the flap base
    base_elev: int          # pos(joint)
    length: int
    tip: Tip
    rect: tuple[int, int, int, int]   # region bounds (ball clipped to paper)

    def elevation(self, x: float, y: float) -> float:
        return self.base_elev + self.length - self.tip.dist(x, y)

    def grad_axis(self, x: float, y: float) -> str:
        """Axis of the elevation gradient at a generic (off-ridge) point."""
        dx = max(0.0, self.tip.x0 - x, x - self.tip.x1)
        dy = max(0.0, self.tip.y0 - y, y - self.tip.y1)
        return "x" if dx > dy else "y"

    def cells(self):
        x0, y0, x1, y1 = self.rect
        return {
            (i, j)
            for i in range(x0, x1)
            for j in range(y0, y1)
        }


@dataclass(frozen=True)
class RiverRegion:
    stick_label: str
    joint_lo: int           # tree node at the low-elevation wall
    joint_hi: int
    base_elev: int          # pos(joint_lo)
    width: int
    rect: tuple[int, int, int, int]
    axis: str               # "v": vertical strip (walls parallel to y)
    lo_side: str            # "min"/"max": which wall is at base_elev

    def elevation(self, x: float, y: float) -> float:
        x0, y0, x1, y1 = self.rect
        c = x if self.axis == "v" else y
        lo = (x0 if self.axis == "v" else y0)
        hi = (x1 if self.axis == "v" else y1)
        d = (c - lo) if self.lo_side == "min" else (hi - c)
        return self.base_elev + d

    def grad_axis(self, x: float, y: float) -> str:
        return "x" if self.axis == "v" else "y"

    def cells(self):
        x0, y0, x1, y1 = self.rect
        return {(i, j) for i in range(x0, x1) for j in range(y0, y1)}

    def wall_joint(self, coord: int) -> int | None:
        """Tree node at a wall line, or None if coord is not a wall."""
        x0, y0, x1, y1 = self.rect
        lo = x0 if self.axis == "v" else y0
        hi = x1 if self.axis == "v" else y1
        if coord == lo:
            return self.joint_lo if self.lo_side == "min" else self.joint_hi
        if coord == hi:
            return self.joint_hi if self.lo_side == "min" else self.joint_lo
        return None


@dataclass
class Packing:
    grid: int
    regions: list          # FlapRegion | RiverRegion
    figure: StickFigure

    def cell_owner(self) -> dict[tuple[int, int], int]:
        owner = {}
        for ri, r in enumerate(self.regions):
            for c in r.cells():
                owner[c] = ri
        return owner


# --------------------------------------------------------------------------
# flap candidate placement
# --------------------------------------------------------------------------

def _flap_candidates(flap: Stick, joint: int, base_elev: int, G: int,
                     pocket: tuple[int, int, int, int]):
    """All valid ball placements of a flap inside a pocket rectangle.

    Tips are integer points or axis-aligned segments (stretch); the ball
    (clipped by the paper border only) must lie inside the pocket.
    """
    l = flap.length
    px0, py0, px1, py1 = pocket
    out = []
    max_stretch = max(px1 - px0, py1 - py0)
    for sx, sy in [(s, 0) for s in range(max_stretch + 1)] + [
        (0, s) for s in range(1, max_stretch + 1)
    ]:
        for tx in range(0, G - sx + 1):
            for ty in range(0, G - sy + 1):
                tip = Tip(tx, ty, tx + sx, ty + sy)
                bx0, by0 = tx - l, ty - l
                bx1, by1 = tx + sx + l, ty + sy + l
                # clip by paper border only
                rx0, ry0 = max(bx0, 0), max(by0, 0)
                rx1, ry1 = min(bx1, G), min(by1, G)
                # clipped ball must lie inside the pocket: any clipping
                # beyond the pocket walls (that are not paper border) is
                # an overlap with another pocket/river.
                if not (px0 <= rx0 and rx1 <= px1 and py0 <= ry0 and ry1 <= py1):
                    continue
                if rx1 - rx0 <= 0 or ry1 - ry0 <= 0:
                    continue
                out.append(
                    FlapRegion(
                        stick_label=flap.label,
                        joint=joint,
                        base_elev=base_elev,
                        length=l,
                        tip=tip,
                        rect=(rx0, ry0, rx1, ry1),
                    )
                )
    return out


def _pack_pocket(flaps: list[tuple[Stick, int, int]], G: int,
                 pocket: tuple[int, int, int, int],
                 max_solutions: int = 4,
                 max_nodes: int = 100_000,
                 deadline: float | None = None) -> list[list[FlapRegion]]:
    """Backtracking search tiling the pocket exactly with flap balls.

    Exact-tiling ordering: branch on the first (row-major) uncovered cell —
    some flap must cover it — over all remaining flaps' candidates that do.
    Flaps of equal length at the same joint are geometrically interchangeable,
    so only the first unplaced flap of each length is branched on.
    """
    px0, py0, px1, py1 = pocket
    pocket_cells = [
        (i, j) for j in range(py0, py1) for i in range(px0, px1)
    ]
    if not flaps and pocket_cells:
        return []
    order = sorted(flaps, key=lambda t: -t[0].length)
    cands = [
        [(c, frozenset(c.cells())) for c in
         _flap_candidates(f, joint, elev, G, pocket)]
        for f, joint, elev in order
    ]
    # cheap infeasibility screens before the exact-tiling search
    if any(not cl for cl in cands):
        return []
    if sum(max(len(cc) for _, cc in cl) for cl in cands) < len(pocket_cells):
        return []
    solutions: list[list[FlapRegion]] = []
    nodes = 0

    def rec(placed_mask: int, used: frozenset, placed: list[FlapRegion]):
        nonlocal nodes
        nodes += 1
        if len(solutions) >= max_solutions or nodes > max_nodes:
            return
        if deadline is not None and nodes % 128 == 0 and time.monotonic() > deadline:
            return
        target = next((c for c in pocket_cells if c not in used), None)
        if target is None:
            if placed_mask == (1 << len(order)) - 1:
                solutions.append(list(placed))
            return
        seen_lengths = set()
        for fi in range(len(order)):
            if placed_mask & (1 << fi):
                continue
            l = order[fi][0].length
            if l in seen_lengths:
                continue
            seen_lengths.add(l)
            for cand, cc in cands[fi]:
                if target not in cc or (cc & used):
                    continue
                placed.append(cand)
                rec(placed_mask | (1 << fi), used | cc, placed)
                placed.pop()
                if len(solutions) >= max_solutions:
                    return

    rec(0, frozenset(), [])
    return solutions


# --------------------------------------------------------------------------
# whole-figure packing
# --------------------------------------------------------------------------

class PackingError(Exception):
    pass


def _positions(sf: StickFigure) -> tuple[int, dict[int, int]]:
    children = {s.child for s in sf.sticks}
    roots = [n for n in sf.nodes if n not in children]
    if len(roots) != 1:
        raise PackingError("sticks must be oriented away from a unique root")
    root = roots[0]
    return root, {n: sf.tree_distance(root, n) for n in sf.nodes}


def _flap_group_joint(flaps: list[Stick]) -> int:
    joints = {f.parent for f in flaps}
    if len(joints) != 1:
        raise PackingError(
            "pocket flaps must share a single joint (star pockets only)"
        )
    return joints.pop()


def pack(sf: StickFigure, G: int, max_solutions: int = 4,
         deadline: float | None = None) -> list[Packing]:
    """All (up to max_solutions) valid packings of the figure on a GxG grid."""
    root, pos = _positions(sf)
    rivers = sf.rivers
    flaps = sf.flaps
    results: list[Packing] = []

    if len(rivers) == 0:
        joint = _flap_group_joint(flaps)
        groups = _pack_pocket(
            [(f, joint, pos[joint]) for f in flaps], G, (0, 0, G, G),
            max_solutions, deadline=deadline,
        )
        results.extend(Packing(G, list(g), sf) for g in groups)

    elif len(rivers) == 1:
        river = rivers[0]
        k = river.length
        u, v = river.parent, river.child   # u nearer the root
        u_flaps = [f for f in flaps if sf.tree_distance(f.parent, u)
                   < sf.tree_distance(f.parent, v)]
        v_flaps = [f for f in flaps if f not in u_flaps]
        ju, jv = _flap_group_joint(u_flaps), _flap_group_joint(v_flaps)
        if ju != u or jv != v:
            raise PackingError("flap groups must attach at the river's joints")

        for axis in ("v", "h"):
            for a in range(1, G - k):
                if deadline is not None and time.monotonic() > deadline:
                    return results
                for flip in (False, True):
                    # river strip [a, a+k] on the chosen axis
                    if axis == "v":
                        r_rect = (a, 0, a + k, G)
                        p_lo, p_hi = (0, 0, a, G), (a + k, 0, G, G)
                    else:
                        r_rect = (0, a, G, a + k)
                        p_lo, p_hi = (0, 0, G, a), (0, a + k, G, G)
                    lo_group, hi_group = (
                        (u_flaps, v_flaps) if not flip else (v_flaps, u_flaps)
                    )
                    lo_side = "min" if not flip else "max"
                    rr = RiverRegion(
                        stick_label=river.label,
                        joint_lo=u,
                        joint_hi=v,
                        base_elev=pos[u],
                        width=k,
                        rect=r_rect,
                        axis=axis,
                        lo_side=lo_side,
                    )
                    lo_joint = u if not flip else v
                    hi_joint = v if not flip else u
                    lo_solutions = _pack_pocket(
                        [(f, lo_joint, pos[lo_joint]) for f in lo_group],
                        G, p_lo, max_solutions, deadline=deadline,
                    )
                    if not lo_solutions:
                        continue
                    hi_solutions = _pack_pocket(
                        [(f, hi_joint, pos[hi_joint]) for f in hi_group],
                        G, p_hi, max_solutions, deadline=deadline,
                    )
                    for gl, gh in itertools.product(lo_solutions, hi_solutions):
                        results.append(Packing(G, [*gl, rr, *gh], sf))
                        if len(results) >= max_solutions:
                            return results
    else:
        raise PackingError("only figures with at most one river are supported")

    return results


def pack_sweep(sf: StickFigure, g_init: int, g_max_extra: int = 6,
               max_solutions: int = 4,
               time_budget: float | None = None) -> tuple[int, list[Packing]]:
    """Paper §4.2: increment the grid size from the heuristic lower bound
    until a valid tiling is found (or the size/time bound is reached)."""
    deadline = None if time_budget is None else time.monotonic() + time_budget
    for G in range(g_init, g_init + g_max_extra + 1):
        packs = pack(sf, G, max_solutions, deadline=deadline)
        if packs:
            return G, packs
        if deadline is not None and time.monotonic() > deadline:
            break
    return -1, []
