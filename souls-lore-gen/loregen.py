"""Lore rendering & elaboration on top of the canon ledger.

Three LLM surfaces, each with an offline template fallback (model=None):

  describe_items  item descriptions (genesis codex, or newly minted items)
  elaborate       enrich a fresh expansion: rewrite skeleton prose, add
                  texture notes — validated and written back into the ledger
  ask_world       answer a question *in-world*, from canon only

The LLM never gets to contradict the ledger: everything it returns is merged
through the ledger's validated mutation paths (unknown entity ids and
malformed additions are dropped, with a warning).
"""

from __future__ import annotations

import json
import random
import sys

from ledger import Ledger, LedgerError, render_chronicle

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
- The world's secrets are layered as numbered VEILS. An item marked
  hints_veil=k may gesture at veil k in at most one clause, deniable and
  oblique — and must never touch any deeper veil. Unmarked items reveal no
  veil at all.
- If an item has a false rumor noted, weave that wrong belief in as if true
  (with at most a soft hedge). Do not signal that it is false.
"""

ELABORATION_GUIDE = """\
You are elaborating one freshly expanded node of the chronicle. You receive
the full canon, the parent event, machine-drafted child events, and any newly
minted items. Your job:

1. Rewrite each child event's text in chronicle register: scholarly-terse,
   30–60 words, past tense, concrete. Keep every established fact — names,
   years, places, outcomes are canon and must not change. You may add small
   texture (a detail, a gesture, a cost) that contradicts nothing.
2. Keep or refine each child's hidden truth if it has one; do not add hidden
   truths to children that lack them.
3. Optionally add up to 4 NOTES: one-sentence texture facts attached to
   EXISTING entity ids (a figure's habit, a faction's custom, what a place
   smells of). Notes become permanent canon — never contradict anything, and
   never state a veil.
4. Write item descriptions for the new items per the style guide.
"""


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------

def _item_payload(lg: Ledger, aid: str) -> dict:
    a = lg.get(aid)
    return {
        "id": aid,
        "name": a["name"],
        "item_type": a["item_type"],
        "created_year": a["created_year"],
        "bias": a["bias"],
        "knowledge": a["knowledge"],
        "false_rumor": a["false_rumor"],
        "hints_veil": a["hints_veil"],
    }


def _veil_block(lg: Ledger) -> str:
    return "\n".join(f"VEIL {i}: {v}" for i, v in enumerate(lg.meta["veils"]))


def _stream_json(model: str, system: str, user: str, schema: dict) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    with client.messages.stream(
        model=model,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=system,
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user}],
    ) as stream:
        message = stream.get_final_message()
    text = next(b.text for b in message.content if b.type == "text")
    return json.loads(text)


# ---------------------------------------------------------------------------
# Item descriptions
# ---------------------------------------------------------------------------

_DESC_SCHEMA = {
    "type": "object",
    "properties": {
        "epigraph": {"type": "string"},
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
}


def describe_items(lg: Ledger, aids: list[str], model: str | None,
                   want_epigraph: bool = False):
    """Fill in `description` on the given artifacts (mutates ledger)."""
    if model is None:
        _fallback_describe(lg, aids, want_epigraph)
        return
    user = (
        "Below is the TRUE hidden chronicle, the numbered veils, and the "
        "items to describe. Each item carries only a fragmentary 'knowledge' "
        "packet; reveal nothing beyond it.\n\n"
        "=== TRUE CHRONICLE ===\n" + render_chronicle(lg) + "\n"
        "=== VEILS ===\n" + _veil_block(lg) + "\n\n"
        "=== ITEMS ===\n" +
        json.dumps([_item_payload(lg, aid) for aid in aids], indent=2) +
        ("\n\nAlso write a 1-2 sentence in-world epigraph for the codex."
         if want_epigraph else "\n\nSet epigraph to an empty string.")
    )
    data = _stream_json(model, STYLE_GUIDE, user, _DESC_SCHEMA)
    for it in data["items"]:
        if it["id"] in lg.entities and it["id"] in aids:
            lg.get(it["id"])["description"] = it["description"]
    if want_epigraph and data.get("epigraph"):
        lg.meta["epigraph"] = data["epigraph"]
    missing = [aid for aid in aids if not lg.get(aid)["description"]]
    if missing:
        _fallback_describe(lg, missing, False)


# -- template fallback ---------------------------------------------------------

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

_VEIL_HINTS = [
    ["Held long enough, it suggests the waning is no accident.",
     "Those who keep it too long begin to doubt the sermons."],
    ["It hums, faintly, as if answering something far below.",
     "In its presence, the old prayers feel like apologies."],
    ["Sometimes, near it, one feels counted — as a debtor is counted.",
     "It is warm the way a held breath is warm: patiently, and not for you."],
]

_DETERMINERS = {"The", "A", "An", "At", "It", "Word", "Pilgrims", "None",
                "For", "Old", "In", "Of", "Twice", "Before"}


def _after_hedge(sentence: str) -> str:
    first = sentence.split(" ", 1)[0]
    if first in _DETERMINERS:
        return sentence[0].lower() + sentence[1:]
    return sentence


def _strip_year(fact: str) -> str:
    if fact.startswith("(year"):
        return fact.split(") ", 1)[1]
    return fact


def _fallback_one(lg: Ledger, aid: str, rng: random.Random) -> str:
    a = lg.get(aid)
    parts = [_FUNCTION_LINES.get(a["item_type"], "A curious thing, of uncertain use.")]
    facts = [f for f in a["knowledge"]
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
    secrets = [f.split("] ", 1)[1] for f in a["knowledge"] if f.startswith("[half-known")]
    if secrets and rng.random() < 0.6:
        parts.append(f"{rng.choice(_HEDGES)} {_after_hedge(secrets[0])}")
    if a["hints_veil"] is not None:
        tier = min(a["hints_veil"], len(_VEIL_HINTS) - 1)
        parts.append(rng.choice(_VEIL_HINTS[tier]))
    parts.append(rng.choice(_CLOSERS))
    return "\n\n".join([parts[0], " ".join(parts[1:])])


def _fallback_describe(lg: Ledger, aids: list[str], want_epigraph: bool):
    rng = random.Random(lg.meta["seed"] ^ 0xC0DE)
    for aid in aids:
        lg.get(aid)["description"] = _fallback_one(lg, aid, rng)
    if want_epigraph:
        lg.meta["epigraph"] = (
            f"Of {lg.meta['primordial']} little now is spoken, and less is true. "
            f"Gather what the old things still remember, and be sparing with belief.")


# ---------------------------------------------------------------------------
# Expansion elaboration (LLM write-back)
# ---------------------------------------------------------------------------

_ELAB_SCHEMA = {
    "type": "object",
    "properties": {
        "children": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "hidden": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                },
                "required": ["id", "text", "hidden"],
                "additionalProperties": False,
            },
        },
        "notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["entity_id", "text"],
                "additionalProperties": False,
            },
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
    "required": ["children", "notes", "items"],
    "additionalProperties": False,
}


def elaborate(lg: Ledger, parent_id: str, child_ids: list[str],
              item_ids: list[str], model: str | None):
    """Enrich a fresh expansion in place. Skeleton survives if the LLM is
    unavailable; LLM output merges only through validated paths."""
    if model is None:
        describe_items(lg, item_ids, None)
        return

    depth = lg.get(child_ids[0])["depth"] if child_ids else 1
    allowed_veil = min(depth, len(lg.meta["veils"]) - 1)
    payload = {
        "parent": {**lg.subgraph([parent_id])[parent_id], "id": parent_id},
        "children": [{**lg.get(c), "id": c} for c in child_ids],
        "new_items": [_item_payload(lg, a) for a in item_ids],
        "related_canon": lg.subgraph([parent_id] + child_ids + item_ids),
        "allowed_veil_index": allowed_veil,
    }
    user = (
        "=== TRUE CHRONICLE ===\n" + render_chronicle(lg) + "\n"
        "=== VEILS ===\n" + _veil_block(lg) + "\n\n"
        f"Nothing you write may state any veil; children's hidden truths and "
        f"new-item hints may gesture only at veils 0..{allowed_veil}.\n\n"
        "=== EXPANSION TO ELABORATE ===\n" +
        json.dumps(payload, indent=2)
    )
    data = _stream_json(model, STYLE_GUIDE + "\n" + ELABORATION_GUIDE,
                        user, _ELAB_SCHEMA)

    for ch in data["children"]:
        if ch["id"] in child_ids and ch["text"].strip():
            rec = lg.get(ch["id"])
            rec["text"] = ch["text"].strip()
            # Only refine an existing hidden truth; never let the LLM mint one.
            if rec["hidden"] and ch["hidden"]:
                rec["hidden"] = ch["hidden"].strip()
    kept = 0
    for note in data["notes"][:4]:
        try:
            lg.add_note(note["entity_id"], note["text"].strip(),
                        f"llm:{parent_id}")
            kept += 1
        except LedgerError as err:
            print(f"  dropped note ({err})", file=sys.stderr)
    for it in data["items"]:
        if it["id"] in item_ids:
            lg.get(it["id"])["description"] = it["description"]
    missing = [a for a in item_ids if not lg.get(a)["description"]]
    if missing:
        _fallback_describe(lg, missing, False)


# ---------------------------------------------------------------------------
# In-world questions
# ---------------------------------------------------------------------------

_ASK_SCHEMA = {
    "type": "object",
    "properties": {
        "fragment": {"type": "string"},
        "attribution": {"type": "string"},
    },
    "required": ["fragment", "attribution"],
    "additionalProperties": False,
}


def _entities_in(lg: Ledger, question: str) -> list[str]:
    q = question.lower()
    return [eid for eid, e in lg.entities.items()
            if e.get("name") and e["name"].lower() in q]


def ask_world(lg: Ledger, question: str, model: str | None) -> str:
    hits = _entities_in(lg, question)
    if model is None:
        if not hits:
            return ("The archivists turn the question over and hand it back: "
                    "no name in it appears in any surviving record.")
        e = lg.get(hits[0])
        rng = random.Random(f"{lg.meta['seed']}:{question}")
        lines = []
        for eid, ev in lg.of_type("event"):
            if hits[0] in ev["participants"]:
                lines.append(f"{rng.choice(_HEDGES)} {_after_hedge(ev['text'])}")
                break
        name = e.get("name", "that one")
        lines.append(f"Of {name}, the records otherwise keep their counsel.")
        return " ".join(lines) + "\n    — a marginal note, unsigned"

    subgraph = lg.subgraph(hits) if hits else {}
    user = (
        "Answer the question below *in-world*: as a fragment someone might "
        "find (a marginal note, a sermon scrap, an interrogation record). "
        "Use ONLY established canon; hedge everything secondhand; never state "
        "any veil. If canon is silent, say so in-world. 40-120 words, plus a "
        "one-line attribution.\n\n"
        "=== TRUE CHRONICLE ===\n" + render_chronicle(lg) + "\n"
        "=== VEILS (forbidden knowledge) ===\n" + _veil_block(lg) + "\n"
        "=== ENTITIES MATCHED IN THE QUESTION ===\n" +
        json.dumps(subgraph, indent=2) + "\n\n"
        f"QUESTION: {question}\n"
    )
    data = _stream_json(model, STYLE_GUIDE, user, _ASK_SCHEMA)
    return f"{data['fragment']}\n    — {data['attribution']}"
