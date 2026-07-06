"""VLM aesthetic judging harness (paper §3.8, Appendix I).

The paper uses Gemini 3 Flash (T=0, single call) with a structured "Rubrics"
prompt in Single Model Evaluation Mode: seven rendered views + the text
prompt in, chain-of-thought + a 0-10 correspondence score out, normalised
to [0, 1] downstream.

In this reproduction the judge model is Claude (the assistant running the
reproduction), evaluating the same seven-view renders under the paper's
verbatim rubric prompt. This is a documented substitution: scores are not
comparable to the paper's Gemini-based numbers, but the harness — prompt,
views, scoring scale, normalisation — matches the paper.
"""

from __future__ import annotations

# Verbatim from the paper, Appendix I (Single Model Evaluation Mode Prompt).
SINGLE_MODEL_RUBRIC_PROMPT = """\
{image_views}
# Role
You are a Rigorous Scientific Origami Judge. Your primary objective is to \
evaluate a 3D-simulated fold based on its anatomical accuracy and biological \
proportions. While technical folding skill is required, anatomical fidelity \
is paramount. Color, shading, and surface patterns are to be entirely \
ignored, as the model is folded from a single sheet of monochrome paper; \
your evaluation must focus exclusively on form, structure, geometry and \
aesthetics.
You must explicitly identify the subject's primary anatomical segments. Any \
model that presents the body as a single, undifferentiated mass without \
clear transitions between major regions (such as Head vs. Thorax) will be \
disqualified.
# Input Data
* **Target Object:** {text_desc}
* **Visual Data:** Multiple 2D snapshots of the final 3D folded state from \
different angles.
# Task
Analyze the provided images to determine how well the folded mesh \
corresponds to the semantic concept of a "{text_desc}". You must look for \
key defining geometric features (e.g., wings for a bird, legs for a table, \
symmetry where applicable).
# Analysis Steps
1. **Feature Identification:** List the visual features visible in the images.
2. **Comparison:** Compare these features against the real-world counterpart \
shape of a {text_desc} (using internal knowledge or provided references). \
You must explicitly verify:
   * Appendage Count: (Primary) Does it have the correct number of appendages?
   * Topology: (Secondary) Do appendages emerge from the correct anatomical \
region (shoulders/hips)?
   * Proportionality: (Tertiary) Are the features scaled correctly relative \
to the real creature?
   * Differentiation: (Quaternary) Is there a clear geometric change between \
the head, neck, and body?
   * Aesthetic Refinement: (Quinary) Are the folds sharp and the symmetry \
balanced?
3. **Flaw Detection:** Identify geometric and structural failures that \
compromise the model's scientific validity.
4. **Scoring:** Assign a score based on the rubric below. Do not penalize \
the model for being monochromatic.
# Scoring Rubric (0-10)
* **0 (Unrecognizable):** The mesh looks like a crumpled ball, flat paper, \
or random noise. No features of a {text_desc} are present.
* **2 (Abstract/Vague):** Vaguely resembles the *mass* of the object, but \
lacks distinct limbs/parts.
* **4 (Poor Correspondence):** Recognizable as an attempt at the target \
subject, but possesses major structural deformities or missing key parts.
* **6 (Fair Correspondence):** Recognizable as the general class of object, \
but contains significant anatomical errors.
* **8 (Good Correspondence):** Strong resemblance and clean folding. Key \
features are present and in the correct numbers, but their shapes may be \
slightly abstracted or blocky.
* **10 (Perfect Correspondence):** A pristine fold that is anatomically \
correct.
# Note
The images are taken from different views, so it is possible that the \
origami looks different or even not recognizable from some views.
Thus, you should pay more attention to the key views that most clearly show \
correspondence.
# Output Format
Provide your reasoning first, then the final score as a number inside angle \
brackets, e.g. <5>.
"""


def build_prompt(text_desc: str, image_note: str = "[seven rendered views attached]") -> str:
    return SINGLE_MODEL_RUBRIC_PROMPT.format(
        image_views=image_note, text_desc=text_desc
    )


def normalise(score_0_10: float) -> float:
    """Paper §3.8: scores are normalised to [0, 1] for selection/reward."""
    return max(0.0, min(1.0, score_0_10 / 10.0))
