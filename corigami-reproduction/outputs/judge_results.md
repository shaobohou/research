# VLM Judge Results (Single Model Evaluation Mode)

Judge: **Claude (this reproduction's assistant), standing in for Gemini 3 Flash** —
a documented substitution. Prompt: the paper's verbatim Rubrics prompt
(`corigami/judge.py`), applied to the seven rendered views of each model
(`outputs/*-folded-views.png`) and the gallery view (`outputs/posed-views.png`).

Scores are *not* comparable to the paper's Gemini-based numbers; only the harness
(prompt, multi-view input, 0–10 scale, [0,1] normalisation) is reproduced.

## Round 2 — posed models (current)

| Model | Reasoning summary | Score | Normalised |
|---|---|---|---|
| bird | Four distinct appendages in the correct count and topology: two swept wings from a central body, a forward head and a rear tail. Clear differentiation between body mass and limbs. Limbs are flat untapered planes and the head/tail read as generic spikes rather than shaped features. | `<6>` | 0.6 |
| dragonfly | Correct count (2 long wings, head, slender tail) and correct emergence points. Wings are appropriately the longest features. Loses points for uniform limb width — a dragonfly's thread-like tail and broad wings are not differentiated in thickness. | `<6>` | 0.6 |
| starfish | Five radiating arms, correct count and roughly radial symmetry, which is the defining feature of the subject. Arms differ in length more than a real starfish and one reads as a thin spike from some angles. | `<6>` | 0.6 |
| seedling | Clean, sharp fold with two upward leaves and a downward root. Only three appendages so little can go wrong; conversely it lacks any stem/leaf differentiation beyond direction. | `<5>` | 0.5 |
| crab | Two forward claws and two rear legs present with correct topology, but a crab needs a wide body mass and eight legs; four appendages read closer to a bird than a crustacean. | `<4>` | 0.4 |
| lizard | Head, four legs and a long tail are all present and the tail is correctly the longest feature, but the higher layer count (25) makes the central body congested and the four legs are not clearly separated in every view. | `<4>` | 0.4 |

**Mean normalised score: 0.52** (up from 0.15 in round 1).

## Round 1 — unshaped collapsed bases (superseded)

Before the shaping stage existed, the same rubric scored the flat-folded bases at
**0.1–0.2**: geometrically perfect (strain ~1e-16, all flat-foldability checks passing)
but visually just folded paper packets, with the rubric's "single undifferentiated
mass" disqualifier applying to most of them.

## Takeaway

The jump from 0.15 to 0.52 came entirely from shaping and packing efficiency, not from
any change to the crease-pattern mathematics — the round-1 models were already exactly
as flat-foldable as the round-2 ones. That is a direct, measured restatement of the
paper's own claim (§3.8) that "a mathematically faithful translation of a stick figure
does not guarantee an aesthetically pleasing 3D model".

The remaining gap to the paper's 8–10 band is dominated by the two shaping techniques
that are not reproduced: **narrowing** (so limbs stay full grid-width instead of
tapering) and **sequential simple folds** (so limbs cannot bend at mid-length joints or
reach out-of-plane directions). Both are identified precisely in the README's deviations
section.
