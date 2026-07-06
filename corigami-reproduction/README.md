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
| Tree-shaping simple folds + clip-pattern narrowing (§3.4–3.6) | ❌ out of scope |
| RL fine-tuning of Gemini 2.5 Flash Lite (§3.6) | ❌ out of scope (requires Gemini training access) |
| Global layer-ordering check (facewise CSP, Akitaya et al.) | ❌ out of scope; strain + local checks + uniaxiality used instead |
| 560k-candidate scale, VLM tournaments, human folding | ❌ out of scope |

## Key results

All five authored example figures pass the full pipeline:

| figure | flaps | rivers | grid | mean axial strain | uniaxiality RMS |
|---|---|---|---|---|---|
| seedling | 3 | 0 | 4 | 2.2e-16 | 3.1e-16 |
| bird | 4 | 1 | 10 | 4.2e-16 | 5.2e-16 |
| human | 5 | 1 | 7 | 3.0e-16 | 4.1e-16 |
| lizard | 6 | 1 | 10 | 3.4e-16 | 5.3e-16 |
| antenna beetle | 6 | 1 | 10 | 3.4e-16 | 7.2e-16 |

For each: every interior vertex satisfies Kawasaki + Maekawa + the crimping test
(Algorithm 1); the geometric simulator folds the solved pattern completely flat with
~1e-16 mean axial strain (the paper's Fig. 15 shows ~1e-5 vertex errors on patterns
with thousands of creases); and a reproduction-specific **uniaxiality check** (RMS of
folded axis position vs. the packing's elevation function, per-region sign fits)
confirms the folded bases realise the target tree. Renders in `outputs/`
(`*-packing.png`, `*-cp.png`, `*-folded-*.png`).

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

`outputs/judge_results.md`: applying the paper's verbatim rubric (with Claude in
place of Gemini 3 Flash), the geometrically perfect but unshaped bases score
0.1–0.2 normalised — a direct illustration of the paper's point that mathematical
fidelity does not yield visual recognisability without the shaping/RL stage.

## Layout

```
corigami-reproduction/
├── corigami/            # the pipeline library
├── scripts/dev_run.py   # single-figure debug harness
├── scripts/run_all.py   # regenerates outputs/ (examples + random batch)
├── tests/               # 20 unit/integration tests
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
4. **No shaping stage**, so folded outputs are collapsed bases (the paper's stage-3
   artifact), not posed models; renders show the flat-folded base with layers separated
   for visibility, plus a 92%-fold view.
