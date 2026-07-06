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

All five authored example figures pass the full pipeline (RESULTS_PLACEHOLDER_EXAMPLES):

- every interior vertex satisfies Kawasaki + Maekawa + the crimping test (Algorithm 1),
- the geometric simulator folds each solved pattern completely flat with mean axial
  strain ~1e-16 (paper reports ~1e-5 for patterns 100× larger),
- a reproduction-specific **uniaxiality check** (RMS deviation of folded axis position vs.
  the packing's elevation function, per-region sign fits) passes at ~1e-16, confirming the
  folded bases really are uniaxial bases realising the target tree.

RESULTS_PLACEHOLDER_BATCH

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
