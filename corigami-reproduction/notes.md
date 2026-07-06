# Notes — COrigami reproduction (arXiv:2606.26299)

## 2026-07-06 — Kickoff

Paper: **COrigami: An AI Pipeline for Co-Designing Flat-Foldable Visually Recognisable Origami**
(Zahavy et al., Google DeepMind — nb. Shaobo Hou, this repo's owner, is a co-author).

Read the full PDF (methods §3, experiments §4, appendices D–I). Pipeline stages:

0. Gemini samples subject from category → text prompt
1. **Stick figure generation** (Gemini, VLM refinement loop) — semantic tree, edges = (label, length, azimuth, elevation); leaves → flaps, internal edges → rivers
2. **Packing** — discrete rectangle packing on integer grid; backtracking over river placements (straight / L-shaped / wall-following) + flap positions; tiling via flap expansion. Grid size heuristic from circle-packing theory (Eq. 1–5)
3. **Solving** — pleat construction (5-step filtering) → deterministic M/V interleaving of pleats → ridge anchor/propagation → greedy combinatorial hinge assignment, scored by local flat-foldability (Kawasaki + Maekawa + crimping, Alg. 1)
4. **Shaping** — tree-shaping algorithm (simple folds via BFS to match stick figure 3D pose); RL-tuned Gemini 2.5 Flash Lite orchestrates narrowing/clip-pattern tools
5. **Folding** — custom geometric simulator: face-adjacency BFS, 4×4 affine per face, vertex averaging, mean axial strain check
6. **VLM feedback** — Gemini 3 Flash judge (rubrics prompt, single-model + comparison/tournament modes)

Paper-scale numbers to compare against: 560k trees → 20.2% valid stick figures → 55.3% packing →
79.2% solving → 92.0% shaping → 5.0% overall survival (27,869 models). VLM judge best acc 0.811.

## Scope decision

Full reproduction is infeasible here (Gemini fine-tuning, RL at scale, 560k candidates, origami artists).
Reproducing the **algorithmic core at small scale**, with the paper's own verification math as ground truth:

- Reproduce faithfully: flat-foldability checks (Kawasaki/Maekawa/crimping Alg. 1), geometric folding
  simulator + mean axial strain, grid heuristic (Eq. 1–5), discrete packing w/ rivers (backtracking),
  crease-pattern solving (pleats → M/V interleave → ridges → greedy hinges), tree similarity (Procrustes),
  per-stage pass-rate accounting (analog of Fig. 6).
- Substitute: Claude (me) authors stick figures + judges renders with the paper's verbatim rubric prompt
  (instead of Gemini); document this clearly.
- Skip: RL fine-tuning, narrowing/clip-pattern templates (stretch goal at best), physical folding.

Verification strategy: construction code is only trusted when the *independent* checkers pass —
every interior vertex must satisfy Kawasaki+Maekawa+crimp, and the folding simulator must fold the CP
flat with ~zero mean axial strain.

## Log

- Env: python3.11, uv available; numpy/matplotlib not preinstalled → pyproject + `uv run`.
- Created project skeleton.

## Design derivation for packing + crease construction (worked out by hand)

The paper packs flaps as rectangles and rivers as width-k paths, then constructs pleats/ridges/hinges.
To make this *provably correct* at small scale I use the elevation-function formulation of uniaxial
box pleating:

- Each region maps paper points to axis positions via e(p). Flap for leaf edge (u,v), length l, with
  **tip** = axis-aligned segment T (possibly a point): region = L-infinity ball {d∞(p,T) <= l} clipped
  only by the paper border; e(p) = pos(u) + l - d∞(p,T). Every non-border boundary point is at exactly
  d∞ = l, i.e. constant elevation pos(u) — so internal boundaries are guaranteed hinge-consistent.
- Straight river for internal edge (u,v), width k: strip; e varies linearly from pos(u) wall to pos(v) wall.
- Validity = exact tiling of the grid + every shared boundary's two regions agree on the tree node at
  that elevation (flap-flap: same base joint; flap-river: river side at the flap's joint; etc.).

Crease catalog (all verified against Kawasaki by hand at the hairy vertices, then machine-checked):
- **Hinges** = internal region boundaries (e-gradient flips across, since e=const on boundary, >0 inside).
- **Ridges** = non-smooth locus of d∞(·,T): 45° segments from each ball corner to the nearest tip
  endpoint, plus the tip segment itself. Straight rivers have no ridges.
- **Pleats** = integer grid edges parallel to the local elevation gradient (the transverse w-field fold
  lines that accordion the paper to a width-1 strip). They refract 90° at ridges, cross hinges straight,
  and terminate only at borders/tips. Constructed per half-cell (cells split by ridge diagonals).

Key hand-verified vertex: flap-ball corner on a river wall, e.g. (6,3) in the bird packing — edges
N,S (wall) + W (flap-flap hinge) + SW (wing ridge) + NW (head ridge) + E (pleat into river):
sectors 90,45,45,45,45,90 → alternating sum 0. Kawasaki holds only because *both* ball corners emit
ridges and the pleat continues through the river. This is why the paper's pleat step 3 keeps segments
"perpendicular to an intersecting hinge".

M/V assignment: paper uses deterministic interleaving + ridge propagation + greedy hinge search with
crimp scoring. I implement it as a backtracking CSP over creases with the paper's deterministic rules
as value-ordering heuristics and Kawasaki/Maekawa/crimp per-vertex pruning — equivalent in spirit
(their greedy search + pruning), complete at our small scale.

Scope restriction: <=1 straight river per figure (all 5 example figures qualify), star flap-groups per
pocket. Documented as a deviation; the paper's wall-following/L-shaped rivers and multi-joint pockets
are out of scope.

## Progress log (implementation)

- Foldability checks + folding simulator implemented first, validated on classic vertices
  (waterbomb 8-fold vertex, big-little-big violations, single/partial folds) — 13 tests.
- Sign convention pinned by partial-fold tests: faces traced CCW → child face right of the
  shared oriented edge → mountain = +pi rotation about it.
- Uniaxiality metric initially fit one global linear map u·f = e + c; wrong for figures with
  rivers (the tree folds onto the axis with per-edge direction flips). Fixed with per-region
  sign fits; all 5 examples then pass at ~1e-16.
- Pocket packer initially enumerated flap-by-flap → 30s+ on 6-flap pockets. Rewrote as
  exact-tiling search (branch on first uncovered cell, dedupe equal-length flaps) → seedling
  0.0s, bird 1.4s, beetle 1.6s end-to-end.
- Random batch needed wall-clock budgets: some candidates provably have no tiling at any grid
  size in the sweep and the exhaustive proof is expensive → deadline threading in the packer
  (20 s/figure), analogous to the paper's bounded sweep.
- All 5 example figures pass end-to-end: strain ~1e-16, uniaxiality RMS ~1e-16, all local
  flat-foldability checks pass. Test suite: 20 passed.
- Renders: CPs look like genuine box-pleated patterns (ridge diagonals, refracting pleats,
  alternating accordion M/V). Partial-fold views of unshaped bases look crumpled, as expected
  (no shaping stage) — added layer-separated flat-fold views for judging instead.

## Final results (2026-07-06)

Batch: 100 random tree candidates (seed 2606), 20 s/figure budget:
- packing 77/100 (77%); solving 77/77 (100%); folding+verification 77/77 (100%).
- Failures all at packing, growing with stick count (8 sticks: 36% pass) — Fig. 7 trend reproduced.
- Solving never fails because the restricted packing class is hinge-consistent by construction;
  the paper's broader packer needs a rejecting solver (79.2%). Documented in README.
- Examples: all 5 pass; strain and uniaxiality RMS both ~1e-16.
- Judge (Claude-as-VLM, paper's verbatim rubric): unshaped bases score 0.1-0.2 normalised, as the
  rubric demands — illustrates why the paper needs the shaping/RL stage.

Interesting reproduction insight: in this formulation "solving" is easy once packing is strict;
the paper's 79.2% solving pass rate is a statement about how permissive their packer is, not about
M/V assignment difficulty per se. At their generality (free-form rivers), strictness at packing
time is presumably impossible to guarantee, hence the staged greedy hinge search.

## Shaping stage: hinge posing (2026-07-06, follow-up)

Feedback: renders looked poor vs the paper. Correct diagnosis — the gap was the missing
shaping stage, not the geometry (my own judge said perfect bases score 0.1-0.2). Implemented
the first and most visually important simple fold of the paper's tree-shaping algorithm:
pivoting each flap out of the base plane at its base hinge.

Math: in a folded uniaxial base a flap's base boundary maps to a single line (the joint's
axis position). Pivoting the flap by delta is a rigid rotation about that line, realised as
a per-crease fold-angle delta on the base-hinge creases. Sign depends on the layer parity of
the *static-side* neighbour face (rotation conjugated through an orientation-reversing map
flips sign) — computed from the flat-folded face normals' z-sign. Global mirror ambiguity
resolved by trying both and keeping the isometric one.

Validated first try: all 5 posed models stay isometric at ~1e-16 strain with flaps lifted
out of plane. Added corigami/shaping.py + tests/test_shaping.py (8 new tests, 28 total).
Posed gallery outputs/posed-views.png — bird now reads as swept wings, lizard as splayed
legs, seedling as a sprout. Pivot angles hand-set from stick-figure limb angles (stand-in
for the paper's RL orchestration). Still no narrowing, so limbs stay full grid-width.
