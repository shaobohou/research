# COrigami Reproduction (arXiv:2606.26299)

Small-scale reproduction of **"COrigami: An AI Pipeline for Co-Designing Flat-Foldable
Visually Recognisable Origami"** (Zahavy et al., 2026) — an end-to-end neuro-symbolic
pipeline that turns a text prompt into a flat-foldable box-pleated origami crease pattern.

## What was reproduced

The paper's pipeline is: text → semantic stick figure (Gemini) → discrete rectangle
packing → flat-foldable crease-pattern solving → shaping (tree-shaping algorithm + RL-tuned
Gemini orchestrating narrowing tools) → geometric folding simulation → VLM aesthetic
judging. This reproduction implements the **algorithmic core end-to-end at small scale**,
with the paper's own verification mathematics used as ground truth at every stage:

| Paper component | Status here |
|---|---|
| Semantic stick figures (§3.1): tree, edges = (label, length, azimuth, elevation) | ✅ `corigami/stickfigure.py` — figures authored by Claude, standing in for the Gemini stage |
| Grid-size heuristic (App. E.1, Eqs. 1–5) | ✅ implemented verbatim |
| Rectangle packing with rivers + flap expansion (§3.2) | ✅ `corigami/packing.py` — backtracking exact-tiling search; restricted to ≤1 straight river, star pockets |
| Crease construction: hinges/ridges/pleats (App. F.1) | ✅ `corigami/solver.py` — derived from the elevation-function formulation (see `notes.md`) |
| M/V solving (§3.3, App. F.2–F.3) | ✅ backtracking CSP with per-vertex Kawasaki/Maekawa/crimp pruning (the paper's greedy search + pruning, made complete at small scale) |
| Flat-foldability checks: Kawasaki, Maekawa, crimping (App. D, Algorithm 1) | ✅ `corigami/foldability.py` — Algorithm 1 implemented as published |
| Geometric folding simulator + mean axial strain (§3.7, App. H) | ✅ `corigami/fold.py` — face-adjacency BFS, per-face 4×4 affine transforms, vertex averaging |
| Tree similarity via Procrustes (App. C.2) | ✅ `corigami/similarity.py` |
| Pipeline pass-rate accounting (Fig. 6/7) | ✅ `corigami/pipeline.py` + `scripts/run_all.py` on random tree candidates |
| VLM judge, Single-Model Rubrics prompt (§3.8, App. I) | ⚠️ harness + verbatim prompt in `corigami/judge.py`; Claude scores the renders instead of Gemini 3 Flash (documented substitution) |
| Shaping — hinge posing + angle derivation (§3.4, App. G) | ✅ `corigami/shaping.py` — flaps pivot at their base hinges; angles derived from the stick figure in closed form; verified isometric (~1e-16 strain) |
| Shaping — the simple fold tool (§3.5) | ✅ `simple_fold()` — cuts the flat-folded base with a line, converts each face intersection into a shaping crease, flipping M/V on orientation-reversed layers |
| Shaping — clip-pattern narrowing with base adapters (§3.5) | ⚠️ `narrow()` narrows the whole base via simple folds and verifies isometry, but without the paper's base adapters it cannot compose with posing (see below) |
| RL orchestration of shaping tools (§3.6) | ❌ out of scope (needs Gemini fine-tuning) |
| Rendering | ✅ `corigami/render3d.py` — own painter's-algorithm renderer; matplotlib's 3D sorting mangles stacked coplanar origami layers |
| RL fine-tuning of Gemini 2.5 Flash Lite (§3.6) | ❌ out of scope (requires Gemini training access) |
| Global layer-ordering check (facewise CSP, Akitaya et al.) | ❌ out of scope; strain + local checks + uniaxiality used instead |
| 560k-candidate scale, VLM tournaments, human folding | ❌ out of scope |

## Key results

All six worked examples pass the full pipeline and are then posed into 3D:

| figure | flaps | rivers | grid (heuristic) | layers | mean axial strain | uniaxiality RMS |
|---|---|---|---|---|---|---|
| bird | 4 | 0 | 8 (8) | 16 | 3.2e-16 | ~1e-16 |
| crab | 4 | 0 | 8 (8) | 16 | 3.2e-16 | ~1e-16 |
| dragonfly | 4 | 0 | 8 (8) | 16 | 3.3e-16 | ~1e-16 |
| starfish | 5 | 0 | 8 (6) | 21 | 3.4e-16 | ~1e-16 |
| seedling | 3 | 0 | 4 (4) | 8 | 2.2e-16 | ~1e-16 |
| lizard | 6 | 1 | 10 (8) | 25 | 3.4e-16 | ~1e-16 |

For each: every interior vertex satisfies Kawasaki + Maekawa + the crimping test
(Algorithm 1); the geometric simulator folds the pattern completely flat at ~1e-16 mean
axial strain (the paper's Fig. 15 reports ~1e-5 on patterns with thousands of creases);
a **uniaxiality check** confirms the folded base realises the target tree; and the posed
model stays isometric at ~1e-16. Gallery: `outputs/posed-views.png`; per-figure
seven-view sheets, packings and crease patterns are in `outputs/`.

**Layers** = paper area / folded footprint, i.e. how efficiently the packing uses the
sheet. It turned out to be the dominant driver of visual quality: an early example set
whose flaps were short relative to the sheet packed at ~33 layers and folded into an
illegible wad, because each individual face was a third of the whole model. Designs that
pack at the heuristic grid bound reach 8–16 layers and read cleanly. This is the
practical meaning of the paper's claim that its packing achieves "optimal use of the
paper by minimizing the required grid size" (§3.2).

### Random-candidate survival (paper Fig. 6/7 analog)

Over 100 random tree candidates in the supported class (`outputs/batch_stats.json`,
charts `outputs/pass-rates.png`, `outputs/failure-by-size.png`):

| stage | this repro (n=100) | paper (n=560k) |
|---|---|---|
| valid packing | **77%** | 55.3% |
| flat-foldable solving | **100%** of packed | 79.2% |
| shaping | — (not implemented) | 92.0% |
| folded + verified (strain < 1e-6) | **100%** of solved | — |

Two observations. First, failures concentrate at the packing stage and grow with
stick count (3–4 sticks: 100% pass; 8 sticks: 36%), reproducing the qualitative
trend of the paper's Fig. 7. Second, solving **never** fails here, unlike the
paper's 79.2%: in our restricted packing class the elevation-function construction
makes internal boundaries hinge-consistent *by design*, so every accepted packing
admits an M/V assignment. The paper's broader packer (wall-following rivers,
multi-joint pockets) accepts layouts whose solvability is not guaranteed — which is
exactly why it needs a solving stage that can reject.

### Judge results

`outputs/judge_results.md`: applying the paper's verbatim rubric (with Claude in place
of Gemini 3 Flash), the posed models score **0.52 mean normalised**, up from **0.15**
for the unshaped collapsed bases. The crease-pattern mathematics is identical in both
rounds — the entire gain came from shaping and packing efficiency, which is a measured
restatement of the paper's own point (§3.8) that "a mathematically faithful translation
of a stick figure does not guarantee an aesthetically pleasing 3D model".

## Layout

```
corigami-reproduction/
├── corigami/            # the pipeline library
├── scripts/dev_run.py   # single-figure debug harness
├── scripts/run_all.py   # regenerates outputs/ (examples + random batch)
├── tests/               # 32 unit/integration tests
├── outputs/             # renders + stats (committed)
└── notes.md             # working log incl. the box-pleating derivation
```

Run: `uv run --extra dev pytest` · `uv run python scripts/run_all.py 150`

## Honest deviations that matter

1. **Stick figures and judging use Claude, not Gemini** — scores are not comparable with
   the paper's Table 2; only the harness (prompt, seven views, 0–10 scale, [0,1]
   normalisation) is reproduced.
2. **Packing is restricted** to ≤1 straight river and star pockets; the paper's
   wall-following rivers, L-shapes, and multi-joint pockets are not implemented. Pass
   rates are therefore not directly comparable with Fig. 6 (55.3% packing), though the
   qualitative trend (failures grow with stick count, Fig. 7) reproduces.
3. **Solving is a complete backtracking CSP** rather than the paper's staged deterministic
   assignment + greedy hinge search. At paper scale their staging is what makes the
   problem tractable; at our scale completeness is affordable and finds the same class of
   solutions.
4. **Partial shaping.** Hinge posing and the simple-fold tool are implemented and
   verified; RL orchestration is not, and narrowing does not yet compose with posing.
   Two consequences are worth stating precisely:

   - *Every hinge in a uniaxial base is parallel*, so a flap has one rotational degree of
     freedom and all flaps swing within a single plane. Mirror-image limbs are therefore
     separated by sending them to opposite sides of that plane, and same-side flaps are
     spread by a minimum angular gap — otherwise limbs that point along the base plane
     want a zero pivot and stay collapsed on top of each other. The paper reaches
     arbitrary limb directions instead by applying simple folds *sequentially*, each one
     re-framing its descendants (App. G); that sequencing is not implemented here.
   - *Narrowing needs base adapters.* `narrow()` produces a valid, isometric narrowed
     pattern, but its creases cross the base hinges, which pins them: posing a narrowed
     flap then breaks isometry (strain jumps to ~5e-3, and the run raises rather than
     returning a bad model). This is exactly the failure the paper's base adapters exist
     to prevent — "the role of the base adapter is to divert narrowing pleats such that
     the rest of the model is not impacted" (App. G.2). Without them, appendages stay
     full grid-width rather than tapering, which is the main remaining visual gap.
