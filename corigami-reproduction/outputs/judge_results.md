# VLM Judge Results (Single Model Evaluation Mode)

Judge: **Claude (this reproduction's assistant), standing in for Gemini 3 Flash** —
documented substitution. Prompt: the paper's verbatim Rubrics prompt
(`corigami/judge.py`), applied to the seven rendered views of each model
(`*-folded-views.png`, `*-folded-flat.png`).

Important context: this reproduction stops at the **collapsed base** (the paper's
stage-3 artifact). The paper's shaping + RL stages, which turn bases into posed,
recognisable models, are out of scope. The rubric is applied as written, so scores
land in the 0–2 band by design — the rubric explicitly maps "flat paper / lacks
distinct limbs" to those scores. That the judge harness assigns low correspondence
scores to unshaped bases is consistent with the paper's premise: aesthetic
recognisability comes from the shaping stage, not the base.

| Model | Prompt | Reasoning summary | Score | Normalised |
|---|---|---|---|---|
| seedling | a sprouting seedling with two leaves and a root | Flat trapezoidal packet; correct flap count (3) is verifiable in the CP/packing but the folded silhouette shows no differentiated leaves/root; reads as folded paper mass. | <2> | 0.2 |
| bird | a soaring bird with spread wings, a head and a tail | Collapsed strip with visible layered flaps; wing/tail/head flaps exist as layers but are stacked coincident — no spread wings or distinct head; vaguely bird-mass at best. | <2> | 0.2 |
| human | a standing human figure with head, two arms and two legs | Flat packet, top view shows strip with diagonal end; five appendage flaps present in structure but undifferentiated in silhouette; disqualified as "single undifferentiated mass" per rubric. | <1> | 0.1 |
| lizard | a lizard with a head, four splayed legs and a long tail | Same failure mode: correct topology internally (verified by uniaxiality/tree checks), zero visual differentiation without shaping. | <1> | 0.1 |
| antenna beetle | a beetle with two long antennae and four legs | Flat packet; layered flaps hint at multiple appendages from edge-on views; no antenna/leg separation visible. | <2> | 0.2 |

## Takeaway

The judge harness reproduces the paper's evaluation *mechanics* and demonstrates the
gap the paper's RL shaping stage is designed to close: geometrically perfect bases
(strain ~1e-16, all flat-foldability checks pass, uniaxiality ~1e-16) still score
0.1–0.2 on visual correspondence. This mirrors the paper's finding that "a
mathematically faithful translation of a stick figure does not guarantee an
aesthetically pleasing 3D model" (§3.8).
