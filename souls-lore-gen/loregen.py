"""Lore rendering layer: true chronicle -> fragmentary item descriptions.

Primary path uses Claude (one batched, streamed call with a JSON-schema
constrained output so cross-item contradictions stay deliberate). A template
fallback keeps the tool usable with no API key.
"""

from __future__ import annotations

import json
import random

from worldsim import World, render_chronicle

DEFAULT_MODEL = "claude-opus-4-8"

STYLE_GUIDE = """\
You write item descriptions in the manner of FromSoftware games (Dark Souls,
Elden Ring): terse, elegiac, third person, past-haunted. Conventions:

- 30–90 words per item. Two parts: a first line stating what the item is or
  does (plain, almost catalogue-like), then one short paragraph of lore.
- Never explain. Imply. End on an unresolved note where it fits — a question
  the reader must carry to other items.
- Hedge secondhand knowledge: "It is said", "Some claim", "The tellings
  differ". State only what the item itself would plausibly "know".
- Proper names are used without introduction, as if the reader should know
  them. Titles and epithets do the work of exposition.
- Grief is understated. No exclamation marks. No modern idiom.
- Items reflect the bias of whoever kept them: a church relic flatters the
  church; a cult trinket accuses the gods; a soldier's ring honours the oath
  and omits the crime.
- Contradictions between items are welcome when their biases differ — that
  is how the true story is meant to be triangulated.
- NEVER state the central mystery outright. Items marked as mystery-hinting
  may gesture at it in at most one clause, deniable and oblique.
- If an item has a false rumor noted, weave that wrong belief in as if true
  (with at most a soft hedge). Do not signal that it is false.
"""


def _items_payload(w: World) -> list[dict]:
    return [
        {
            "id": a.id,
            "name": a.name,
            "item_type": a.item_type,
            "created_year": a.created_year,
            "bias": a.bias,
            "knowledge": a.knowledge,
            "false_rumor": a.false_rumor,
            "may_hint_at_mystery": a.hints_mystery,
        }
        for a in w.artifacts
    ]


def _build_user_prompt(w: World) -> str:
    return (
        "Below is the TRUE hidden chronicle of a procedurally generated world, "
        "followed by the list of items to describe. Each item carries only a "
        "fragmentary 'knowledge' packet (what it plausibly knows), a bias, "
        "optionally a false rumor to embed, and a flag for whether it may hint "
        "at the central mystery.\n\n"
        "Write one description per item, following the style guide exactly. "
        "Use the chronicle for coherence (correct names, correct relationships), "
        "but each description may only reveal what its own knowledge packet "
        "supports.\n\n"
        "=== TRUE CHRONICLE (never to be revealed directly) ===\n"
        f"{render_chronicle(w)}\n"
        "=== ITEMS ===\n"
        f"{json.dumps(_items_payload(w), indent=2)}\n"
    )


_OUTPUT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "epigraph": {
                "type": "string",
                "description": "A 1-2 sentence epigraph for the codex, in-world voice.",
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["id", "description"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["epigraph", "items"],
        "additionalProperties": False,
    },
}


def llm_descriptions(w: World, model: str = DEFAULT_MODEL) -> tuple[str, dict[str, str]]:
    """Return (epigraph, {artifact_id: description}) via one batched Claude call."""
    import anthropic

    client = anthropic.Anthropic()
    with client.messages.stream(
        model=model,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=STYLE_GUIDE,
        output_config={"format": _OUTPUT_SCHEMA},
        messages=[{"role": "user", "content": _build_user_prompt(w)}],
    ) as stream:
        message = stream.get_final_message()

    text = next(b.text for b in message.content if b.type == "text")
    data = json.loads(text)
    return data["epigraph"], {it["id"]: it["description"] for it in data["items"]}


# ---------------------------------------------------------------------------
# Template fallback (no API key required)
# ---------------------------------------------------------------------------

_FUNCTION_LINES = {
    "weapon": "A weapon of an older make, still keen despite its years.",
    "armor": "Worn armor that remembers the shape of its last bearer.",
    "ring": "A ring that grants a small, stubborn blessing.",
    "talisman": "A talisman for the invoking of half-forgotten rites.",
    "soul remnant": "The lingering soul of one who would not wholly pass.",
    "key item": "An object of no use in battle, and of great consequence.",
    "consumable": "A humble ward, spent in a moment.",
    "catalyst": "A catalyst attuned to the old gift.",
}

_HEDGES = ["It is said that", "Some claim", "The tellings differ, but most agree",
           "Old verses hold that", "None now living can say whether"]

_CLOSERS = [
    "What became of it after is not written.",
    "The rest of the story is kept by no one.",
    "Whether this was mercy or malice, none agree.",
    "The name endures; little else does.",
    "Perhaps it is better that the tale ends there.",
]

_MYSTERY_HINTS = [
    "Held long enough, it suggests the waning is no accident.",
    "Those who keep it too long begin to doubt the sermons.",
    "It hums, faintly, as if answering something far below.",
    "In its presence, the old prayers feel like apologies.",
]


def _strip_year(fact: str) -> str:
    if fact.startswith("(year"):
        return fact.split(") ", 1)[1]
    return fact


_DETERMINERS = {"The", "A", "An", "At", "It", "Word", "Pilgrims", "None", "For", "Old"}


def _after_hedge(sentence: str) -> str:
    """Lowercase the leading word only when it isn't a proper name."""
    first = sentence.split(" ", 1)[0]
    if first in _DETERMINERS:
        return sentence[0].lower() + sentence[1:]
    return sentence


def fallback_descriptions(w: World) -> tuple[str, dict[str, str]]:
    """Deterministic template renderer mirroring the LLM constraints."""
    rng = random.Random(w.seed ^ 0xC0DE)
    out: dict[str, str] = {}
    for a in w.artifacts:
        parts = [_FUNCTION_LINES[a.item_type]]
        facts = [f for f in a.knowledge
                 if not f.startswith("[half-known") and not f.startswith("The affliction")]
        events = [_strip_year(f) for f in facts if f.startswith("(year")]
        others = [f for f in facts if not f.startswith("(year")]
        if events:
            parts.append(events[0])
        if len(events) > 1 and rng.random() < 0.7:
            parts.append(f"{rng.choice(_HEDGES)} {_after_hedge(events[1])}")
        else:
            fate = next((o for o in others if ": fate —" in o), None)
            if fate and fate.split(",", 1)[0] not in " ".join(parts):
                name, rest = fate.split(": fate —", 1)
                rest = rest.strip().rstrip(".")
                if "(year" in rest:
                    rest = rest.split(" (year", 1)[0]
                parts.append(f"Of {name}, the last word is this: {rest}.")
        secrets = [f.split("] ", 1)[1] for f in a.knowledge if f.startswith("[half-known")]
        if secrets and rng.random() < 0.6:
            parts.append(f"{rng.choice(_HEDGES)} {_after_hedge(secrets[0])}")
        if a.hints_mystery:
            parts.append(rng.choice(_MYSTERY_HINTS))
        parts.append(rng.choice(_CLOSERS))
        out[a.id] = "\n\n".join([parts[0], " ".join(parts[1:])])

    epigraph = (f"Of {w.primordial_name} little now is spoken, and less is true. "
                f"Gather what the old things still remember, and be sparing with belief.")
    return epigraph, out


# ---------------------------------------------------------------------------
# Codex rendering
# ---------------------------------------------------------------------------

def render_codex(w: World, epigraph: str, descs: dict[str, str]) -> str:
    lines = [f"# Codex of Found Things (seed {w.seed})", ""]
    lines.append(f"*{epigraph}*")
    lines.append("")
    by_type: dict[str, list] = {}
    for a in w.artifacts:
        by_type.setdefault(a.item_type, []).append(a)
    for itype in sorted(by_type):
        lines.append(f"## {itype.title()}s" if not itype.endswith("s") else f"## {itype.title()}")
        lines.append("")
        for a in by_type[itype]:
            lines.append(f"### {a.name}")
            lines.append("")
            lines.append(descs.get(a.id, "(no description generated)"))
            lines.append("")
    return "\n".join(lines)
