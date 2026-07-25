"""Semantic stick figures (paper §3.1) and the grid-size heuristic (Appendix E.1).

A semantic stick figure is a tree whose edges ("sticks") each carry a label,
an integer length (grid units), and 3D orientation (azimuth/elevation in
degrees). Leaf edges map to box-pleating flaps; internal edges map to rivers.

In the paper these are sampled by Gemini under a constrained prompt workflow
with a VLM refinement loop; here the example figures are authored by Claude
(the assistant running this reproduction), standing in for that stage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Stick:
    label: str
    parent: int          # node id nearer the root
    child: int           # node id further from the root
    length: int          # grid units
    azimuth: float       # degrees, CCW from +x in the ground plane
    elevation: float     # degrees above the ground plane

    def direction(self) -> np.ndarray:
        az, el = math.radians(self.azimuth), math.radians(self.elevation)
        return np.array(
            [
                math.cos(el) * math.cos(az),
                math.cos(el) * math.sin(az),
                math.sin(el),
            ]
        )


@dataclass
class StickFigure:
    name: str
    prompt: str                       # the natural-language target subject
    sticks: list[Stick] = field(default_factory=list)

    # ------------------------------------------------------------ topology

    @property
    def nodes(self) -> set[int]:
        out = set()
        for s in self.sticks:
            out.add(s.parent)
            out.add(s.child)
        return out

    def degree(self, node: int) -> int:
        return sum(1 for s in self.sticks if node in (s.parent, s.child))

    def is_leaf_stick(self, s: Stick) -> bool:
        """Leaf sticks (flaps) end at a degree-1 node."""
        return self.degree(s.child) == 1

    @property
    def flaps(self) -> list[Stick]:
        return [s for s in self.sticks if self.is_leaf_stick(s)]

    @property
    def rivers(self) -> list[Stick]:
        return [s for s in self.sticks if not self.is_leaf_stick(s)]

    def validate(self) -> list[str]:
        """Constrained-workflow topology checks (acyclic, connected, labels)."""
        errors = []
        nodes = self.nodes
        if len(self.sticks) != len(nodes) - 1:
            errors.append("edge count != node count - 1 (cycle or forest)")
        # connectivity
        adj: dict[int, list[int]] = {}
        for s in self.sticks:
            adj.setdefault(s.parent, []).append(s.child)
            adj.setdefault(s.child, []).append(s.parent)
        if nodes:
            seen, stack = set(), [next(iter(nodes))]
            while stack:
                n = stack.pop()
                if n in seen:
                    continue
                seen.add(n)
                stack.extend(adj.get(n, []))
            if seen != nodes:
                errors.append("stick figure is not connected")
        labels = [s.label for s in self.sticks]
        if len(labels) != len(set(labels)):
            errors.append("stick labels are not unique")
        if any(s.length <= 0 for s in self.sticks):
            errors.append("stick lengths must be positive integers")
        return errors

    # ---------------------------------------------------------- geometry

    def joint_positions(self, root: int = 0) -> dict[int, np.ndarray]:
        """3D joint coordinates by walking sticks from the root."""
        pos = {root: np.zeros(3)}
        remaining = list(self.sticks)
        while remaining:
            progressed = False
            for s in list(remaining):
                if s.parent in pos:
                    pos[s.child] = pos[s.parent] + s.length * s.direction()
                    remaining.remove(s)
                    progressed = True
                elif s.child in pos:
                    pos[s.parent] = pos[s.child] - s.length * s.direction()
                    remaining.remove(s)
                    progressed = True
            if not progressed:
                raise ValueError("disconnected stick figure")
        return pos

    def tree_distance(self, a: int, b: int) -> int:
        """Path length between nodes, weighted by stick length."""
        adj: dict[int, list[tuple[int, int]]] = {}
        for s in self.sticks:
            adj.setdefault(s.parent, []).append((s.child, s.length))
            adj.setdefault(s.child, []).append((s.parent, s.length))
        # BFS (tree: unique path)
        stack = [(a, 0)]
        seen = {a}
        while stack:
            n, d = stack.pop()
            if n == b:
                return d
            for m, w in adj.get(n, []):
                if m not in seen:
                    seen.add(m)
                    stack.append((m, d + w))
        raise ValueError("nodes not connected")

    def diameter(self) -> int:
        """Longest path in the tree weighted by stick length."""
        nodes = list(self.nodes)
        far = max(nodes, key=lambda n: self.tree_distance(nodes[0], n))
        return max(self.tree_distance(far, n) for n in nodes)


def grid_size_heuristic(sf: StickFigure, symmetric: bool = False) -> int:
    """Appendix E.1, Eqs. (1)-(5): heuristic lower bound on the grid size."""
    flaps = sorted(sf.flaps, key=lambda s: -s.length)
    rivers = sf.rivers
    river_set = {id(s) for s in rivers}

    def endpoint_neighbors(stick: Stick) -> list[Stick]:
        out = []
        for s in sf.sticks:
            if s is stick:
                continue
            if {s.parent, s.child} & {stick.parent, stick.child}:
                out.append(s)
        return out

    areas = []
    for i, f in enumerate(flaps):
        if i < 4:
            areas.append(f.length**2)          # quarter-circle corner packing
        else:
            areas.append(2 * f.length**2)      # conservative default
    for r in rivers:
        nbrs = endpoint_neighbors(r)
        if all(id(n) not in river_set for n in nbrs):
            m = max(n.length for n in nbrs)
            areas.append(max(r.length * m, r.length**2))
        else:
            areas.append(r.length**2)

    g = max(math.ceil(math.sqrt(sum(areas))), sf.diameter())
    if symmetric and g % 2 == 1:
        g += 1
    return g


# ---------------------------------------------------------------------------
# Example figures (Claude-authored, standing in for the Gemini stage).
# Lengths in grid units; azimuth/elevation guide the (future) shaping stage.
# ---------------------------------------------------------------------------

def example_figures() -> list[StickFigure]:
    """Worked examples (Claude-authored, standing in for the Gemini stage).

    Lengths are chosen so the packer reaches its heuristic grid bound, which
    keeps the folded base thin (8-16 layers rather than 30+) — the paper's
    "optimal use of the paper by minimising the required grid size". The
    lizard keeps a river to exercise that path, at the cost of efficiency.
    """
    def star(name, prompt, specs):
        return StickFigure(name, prompt, [
            Stick(label, 0, i + 1, length, azimuth, elevation)
            for i, (label, length, azimuth, elevation) in enumerate(specs)
        ])

    return [
        star("bird", "a bird with two spread wings, a head and a tail", [
            ("head", 3, 0, 25),
            ("left wing", 4, 100, 5),
            ("right wing", 4, -100, 5),
            ("tail", 3, 180, -20),
        ]),
        star("crab", "a crab with two big claws and a pair of legs", [
            ("left claw", 4, 55, 15),
            ("right claw", 4, -55, 15),
            ("left leg", 3, 130, -25),
            ("right leg", 3, -130, -25),
        ]),
        star("dragonfly", "a dragonfly with long wings, a head and a slender tail", [
            ("left wing", 4, 95, 8),
            ("right wing", 4, -95, 8),
            ("head", 3, 0, 15),
            ("tail", 4, 180, -8),
        ]),
        star("starfish", "a five-armed starfish", [
            ("arm one", 3, 90, 10),
            ("arm two", 3, 162, 10),
            ("arm three", 2, 234, 10),
            ("arm four", 2, 306, 10),
            ("arm five", 2, 18, 10),
        ]),
        star("seedling", "a sprouting seedling with two leaves and a root", [
            ("left leaf", 2, 130, 40),
            ("right leaf", 2, 50, 40),
            ("root", 2, 180, -85),
        ]),
        # keeps a river in the example set (packs less efficiently, by design)
        StickFigure(
            name="lizard",
            prompt="a lizard with a head, four splayed legs and a long tail",
            sticks=[
                Stick("head", 1, 2, 2, 0, 10),
                Stick("front left leg", 1, 3, 2, 120, -20),
                Stick("front right leg", 1, 4, 2, -120, -20),
                Stick("body", 1, 0, 2, 180, 0),   # river
                Stick("hind left leg", 0, 5, 2, 60, -20),
                Stick("hind right leg", 0, 6, 2, -60, -20),
                Stick("tail", 0, 7, 4, 180, 0),
            ],
        ),
    ]
