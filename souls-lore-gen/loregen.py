"""Lore rendering & elaboration on top of the canon ledger.

All prose in this system is written by Claude. There is no template writer:
a world without a working model is not generated at all, rather than
generated badly. Three surfaces:

  describe_items  item descriptions (genesis codex, or newly minted items)
  elaborate       enrich a fresh expansion: rewrite skeleton prose, add
                  texture notes — validated and written back into the ledger
  ask_world       answer a question *in-world*, from canon only

The LLM never gets to contradict the ledger: everything it returns is merged
through the ledger's validated mutation paths (unknown entity ids and
malformed additions are dropped, with a warning). The *facts* are simulated
and deterministic; only their telling is generated.
"""

from __future__ import annotations

import json
import sys

from ledger import Ledger, LedgerError, render_chronicle

DEFAULT_MODEL = "claude-opus-4-8"


class NoCredentials(RuntimeError):
    """Raised when no Claude credentials are available."""


_NO_CREDS_MSG = (
    "Claude credentials are required — this generator has no offline mode. "
    "Set ANTHROPIC_API_KEY, or run `ant auth login`."
)


def _client():
    """An Anthropic client. Credentials resolve from ANTHROPIC_API_KEY,
    ANTHROPIC_AUTH_TOKEN, or an `ant auth login` profile — so an unset env var
    alone does not mean unauthenticated. The SDK defers the auth check to
    request time, so the clear error is raised in `_stream_json` below."""
    import anthropic
    return anthropic.Anthropic()

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

    client = _client()
    try:
        with client.messages.stream(
            model=model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=system,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": user}],
        ) as stream:
            message = stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise NoCredentials(_NO_CREDS_MSG) from e
    except TypeError as e:                  # SDK's unresolved-auth guard
        if "authentication" in str(e).lower():
            raise NoCredentials(_NO_CREDS_MSG) from e
        raise
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


def _describe_call(lg: Ledger, aids: list[str], model: str,
                   want_epigraph: bool) -> dict:
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
    return _stream_json(model, STYLE_GUIDE, user, _DESC_SCHEMA)


def describe_items(lg: Ledger, aids: list[str], model: str = DEFAULT_MODEL,
                   want_epigraph: bool = False):
    """Fill in `description` on the given artifacts (mutates ledger).

    If the model omits items, one repair pass asks for just those; a second
    shortfall is an error rather than a silently half-written codex."""
    data = _describe_call(lg, aids, model, want_epigraph)
    for it in data["items"]:
        if it["id"] in lg.entities and it["id"] in aids:
            lg.get(it["id"])["description"] = it["description"]
    if want_epigraph and data.get("epigraph"):
        lg.meta["epigraph"] = data["epigraph"]

    missing = [aid for aid in aids if not lg.get(aid)["description"]]
    if missing:
        print(f"  {len(missing)} item(s) undescribed; asking again",
              file=sys.stderr)
        data = _describe_call(lg, missing, model, False)
        for it in data["items"]:
            if it["id"] in missing:
                lg.get(it["id"])["description"] = it["description"]
        still = [aid for aid in aids if not lg.get(aid)["description"]]
        if still:
            raise RuntimeError(
                f"model did not describe {len(still)} item(s) after a repair "
                f"pass: {', '.join(lg.get(a)['name'] for a in still)}")



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
              item_ids: list[str], model: str = DEFAULT_MODEL):
    """Enrich a fresh expansion in place. The deterministic skeleton is
    already committed to the ledger before this runs, so a failed call loses
    prose, never canon; LLM output merges only through validated paths."""
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
        describe_items(lg, missing, model)      # repair pass, same contract


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


def ask_world(lg: Ledger, question: str, model: str = DEFAULT_MODEL) -> str:
    hits = _entities_in(lg, question)
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


# ---------------------------------------------------------------------------
# Witnesses: the player-facing voice. These two functions are the ONLY ones a
# player's actions reach, and neither is given the chronicle or the veils —
# they receive a persona and a list of belief texts, nothing else. Leakage is
# therefore impossible by construction rather than forbidden by instruction.
# ---------------------------------------------------------------------------

WITNESS_GUIDE = """\
You voice one inhabitant of a dying world, speaking aloud to a stranger who
has asked them something. Rules:

- You know ONLY the beliefs listed for you. They are what you hold to be true.
  Some may be wrong; you have no way to tell which, and you never hedge a
  belief on the grounds that it might be false.
- Never invent a new fact, name, date, or event. If the beliefs do not cover
  what was asked, say so in your own voice and stop.
- Speak in first person, 40–110 words, in the register of your manner and
  bias. Plain, worn, unliterary. No modern idiom, no exclamation marks.
- You are not a narrator and not an archive. You are a person with a job,
  interrupted.
- If you "will not speak of something", and the question circles near the
  thing you refuse, break off rather than explain — go quiet, change the
  subject, ask them to leave. Do not hint at content.
"""

_WITNESS_SCHEMA = {
    "type": "object",
    "properties": {"speech": {"type": "string"}},
    "required": ["speech"],
    "additionalProperties": False,
}


def witness_reply(speaker: dict, question: str, relevant: list[str],
                  knows_nothing: bool, model: str = DEFAULT_MODEL) -> str:
    """What this witness says when asked. `relevant` are the belief texts that
    bear on the question; `knows_nothing` means none did."""
    user = (
        "=== WHO YOU ARE ===\n" + json.dumps(speaker, indent=2) + "\n\n"
        "=== WHAT BEARS ON THE QUESTION ===\n" +
        (json.dumps(relevant, indent=2) if relevant else
         "(nothing you hold bears on this)") + "\n\n"
        "=== THEY ASKED ===\n" + question + "\n\n" +
        ("You do not know. Say so in character, briefly, and do not guess."
         if knows_nothing else
         "Answer from those beliefs only, in your own voice.")
    )
    return _stream_json(model, WITNESS_GUIDE, user, _WITNESS_SCHEMA)["speech"]


_REACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "reactions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "stance": {"type": "string",
                               "enum": ["agrees", "disputes", "never heard",
                                        "will not say"]},
                    "speech": {"type": "string"},
                },
                "required": ["claim", "stance", "speech"],
                "additionalProperties": False,
            },
        },
        "closing": {"type": "string"},
    },
    "required": ["reactions", "closing"],
    "additionalProperties": False,
}

CONFIDE_GUIDE = """\
A stranger is telling you what they think happened. React to each of their
claims using ONLY your own beliefs as the measure:

- agrees      — it matches something you hold. Say so warmly or grudgingly.
- disputes    — it contradicts something you hold. Push back with confidence,
                and say what you believe instead. You may well be the one who
                is wrong; you will never suspect it.
- never heard — your beliefs simply do not touch it. Do not evaluate it. Do
                not guess whether it sounds likely.
- will not say — only if you "will not speak of something" and the claim
                circles it. Break off; reveal nothing about why.

You are not a judge and there is no correct answer. Never say "true", "false",
"correct", or "you are right". 20–50 words per reaction, first person, in your
manner. Then one closing line as the conversation ends.
"""


def witness_reaction(speaker: dict, claims: list[str],
                     model: str = DEFAULT_MODEL) -> dict:
    """How this witness receives a stranger's theory. Measured against their
    beliefs — so they can endorse a falsehood they hold and dismiss a truth
    they have never encountered."""
    user = ("=== WHO YOU ARE ===\n" + json.dumps(speaker, indent=2) + "\n\n"
            "=== WHAT THEY CLAIM ===\n" + json.dumps(claims, indent=2))
    return _stream_json(model, WITNESS_GUIDE + "\n" + CONFIDE_GUIDE,
                        user, _REACTION_SCHEMA)
