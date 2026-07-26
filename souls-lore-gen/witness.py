"""Living witnesses: bounded, unreliable people you can actually talk to.

There is no oracle in this world. Nothing answers questions "from canon" —
answers come from a *person standing in front of you*, and a person knows
only what their line witnessed, what their institution teaches, and what they
have heard. Most of it is true. Some of it is wrong in ways they cannot tell
from the rest.

Two facts about a dusk world do most of the design work:

  Everyone who was there is dead. The gods are gone, the kings are slain, the
  saint was spent. So you never speak to a witness — you speak to an
  *inheritor*, whose knowledge arrived through however many mouths, degraded.

  Institutions remember what suits them. A church's doctrine is a belief like
  any other in its keeper's head, indistinguishable to them from what their
  order actually saw.

Each witness therefore carries a list of BELIEFS. A belief has text, a
provenance kind (witnessed / inherited / doctrine / rumor), and a server-side
`true` flag used only by the benchmark and by selfcheck — never shown, never
sent to the model that speaks for them. What the model receives is the belief
text and the persona. It cannot leak the chronicle because it is never given
the chronicle.

Generation is deterministic per (seed, faction) and idempotent, like
ensure_geography: call `ensure_witnesses(lg)` after any world change.
"""

from __future__ import annotations

import random

from ledger import Ledger
from worldsim import BIAS_BY_KIND, Namer

# Who survives to be spoken to, per faction kind, and how they hold knowledge.
_INHERITOR = {
    "church": ("keeper of the reliquary",
               "devout; repeats the sermon as fact and resents the asking"),
    "order":  ("last-sworn of the order",
               "plain, dutiful, precise about oaths and vague about miracles"),
    "cult":   ("pilgrim of the cult",
               "eager, conspiratorial, certain of things they cannot support"),
    "kingdom": ("hedge-knight of a fallen house",
                "proud, bitter, protective of the dead king's name"),
}

_DOCTRINE = {
    # (statement, is_it_actually_true)
    "church": [("The waning is a trial, and the faithful will be spared it.", False),
               ("The rite of restoration was a mercy, and it worked.", False)],
    "order":  [("An oath outlasts the one who swore it. That is all we have.", True),
               ("No miracle has ever held back the affliction. Only vigilance.", True)],
    "cult":   [("The gods made the waning. They have never once denied it.", True),
               ("Those the cult marks are spared the affliction.", False)],
    "kingdom": [("The king was betrayed by one man, and the realm was blameless.", False),
                ("The crown was carried off, not surrendered.", True)],
}

_DEFLECTIONS = [
    "That name means nothing to me. Ask at a house that keeps such records.",
    "I have not heard it, and I would have heard it.",
    "You are asking the wrong door. I know my own dead, no others.",
    "If it was written down, it was not written down here.",
]


# ---------------------------------------------------------------------------
# Distortion: how knowledge degrades on its way down a lineage
# ---------------------------------------------------------------------------

def _distort(rng: random.Random, lg: Ledger, text: str,
             other_names: list[str]) -> tuple[str, str]:
    """Return (distorted_text, what_went_wrong). Never signals the error."""
    import re

    kinds = []
    names_in = [n for n in other_names if n in text]
    years = re.findall(r"\b(\d{2,3})\b", text)
    if names_in:
        kinds.append("actor")
    if years:
        kinds.append("year")
    kinds.append("survivor")
    kind = rng.choice(kinds)

    if kind == "actor":
        wrong = rng.choice([n for n in other_names if n not in names_in]
                           or other_names)
        return text.replace(names_in[0], wrong, 1), f"names {wrong} for {names_in[0]}"
    if kind == "year":
        y = years[0]
        shifted = str(max(1, int(y) + rng.choice([-120, -60, 60, 120])))
        return text.replace(y, shifted, 1), f"misdates it to year {shifted}"
    subject = names_in[0] if names_in else "the one in question"
    return (text.rstrip(".") + f". And {subject} is not dead — that part is a lie "
            f"the histories tell.", f"insists {subject} still lives")


# ---------------------------------------------------------------------------
# Building the cast
# ---------------------------------------------------------------------------

def ensure_witnesses(lg: Ledger) -> bool:
    """Create one living inheritor per surviving institution, each with a
    bounded belief set. Idempotent; returns True if the ledger changed."""
    store = lg.d.setdefault("witnesses", {})
    factions = lg.of_type("faction")
    have = {w["faction"] for w in store.values() if w.get("faction")}
    changed = False

    all_names = [f["name"] for _, f in lg.of_type("figure")]

    for kid, k in factions:
        if kid in have:
            continue
        rng = random.Random(f"{lg.meta['seed']}:witness:{kid}")
        namer = Namer(rng, used=set(lg.meta["used_names"]))
        role, manner = _INHERITOR.get(k["kind"], _INHERITOR["order"])
        name = namer.person()
        fid = lg.add_figure(name, f"the {rng.choice(['Grey', 'Younger', 'Sleepless', 'Patient', 'Last'])}",
                            role, kid, depth=0, source="witness")
        site = lg.find_place(k["seat"])[0]

        beliefs: list[dict] = []

        # 1. Doctrine — held as firmly as anything, true or not.
        for text, truth in _DOCTRINE.get(k["kind"], []):
            beliefs.append({"text": text, "kind": "doctrine", "true": truth,
                            "about": [kid]})

        # 2. Inherited accounts: events this institution figured in. Retold at
        #    a remove, and roughly a third of them wrong in some detail.
        related = []
        for eid, e in lg.of_type("event"):
            touches = k["name"] in e["text"] or k["seat"] in e["text"]
            if not touches:
                for pid in e["participants"]:
                    if lg.get(pid).get("faction") == kid:
                        touches = True
                        break
            if touches:
                related.append((eid, e))
        related.sort(key=lambda p: p[1]["year"])
        for eid, e in related[:6]:
            about = [eid] + e["participants"] + e.get("referents", [])
            if rng.random() < 0.34:
                text, wrong = _distort(rng, lg, e["text"], all_names)
                beliefs.append({"text": text, "kind": "inherited",
                                "true": False, "distortion": wrong,
                                "about": about})
            else:
                beliefs.append({"text": e["text"], "kind": "inherited",
                                "true": True, "about": about})

        # 3. A rumor of their own, always false, never flagged to the player.
        if related:
            eid, e = rng.choice(related)
            subject = rng.choice(all_names)
            beliefs.append({
                "text": (f"They say {subject} was seen after all this, walking "
                         f"and whole. I believe it."),
                "kind": "rumor", "true": False, "about": [eid]})

        # 4. Veil adjacency is a *character trait*, not a detector: exactly one
        #    witness per world has stood close enough to a buried thing to go
        #    quiet about it. Everyone else simply shrugs.
        beliefs_touch_veil = False

        store[fid] = {
            "name": name, "role": role, "manner": manner,
            "faction": kid, "faction_name": k["name"], "faction_kind": k["kind"],
            "site": site, "bias": BIAS_BY_KIND[k["kind"]],
            "beliefs": beliefs, "veil_touched": beliefs_touch_veil,
        }
        changed = True

    # assign the single veil-touched witness deterministically
    if store and not any(w.get("veil_touched") for w in store.values()):
        rng = random.Random(f"{lg.meta['seed']}:veilwitness")
        # prefer a cult or church inheritor: those are the ones who dig or pray
        pool = [fid for fid, w in sorted(store.items())
                if w["faction_kind"] in ("cult", "church")] or sorted(store)
        chosen = rng.choice(pool)
        store[chosen]["veil_touched"] = True
        store[chosen]["beliefs"].append({
            "text": ("There is a thing beneath all of this that I will not "
                     "name. I came close to it once and I have not slept the "
                     "same since."),
            "kind": "witnessed", "true": True, "about": []})
        changed = True

    return changed


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def witnesses_at(lg: Ledger, place_id: str) -> list[tuple[str, dict]]:
    return sorted(((fid, w) for fid, w in lg.d.get("witnesses", {}).items()
                   if w["site"] == place_id), key=lambda p: p[1]["name"])


def bearing_on(lg: Ledger, w: dict, question: str) -> list[dict]:
    """Which of this witness's beliefs bear on the question — by the names
    they share. A witness who knows nothing relevant says so."""
    q = question.lower()
    named = {eid for eid, e in lg.entities.items()
             if e.get("name") and e["name"].lower() in q}
    out = []
    for b in w["beliefs"]:
        if b["kind"] == "doctrine":
            continue
        if named & set(b["about"]) or any(
                lg.get(i)["name"].lower() in q
                for i in b["about"] if i in lg.entities
                and lg.entities[i].get("name")):
            out.append(b)
    return out


def deflection(lg: Ledger, w: dict, question: str) -> str:
    rng = random.Random(f"{lg.meta['seed']}:{w['name']}:{question}")
    return f"{rng.choice(_DEFLECTIONS)}"


def speakable(w: dict) -> dict:
    """Exactly what may be sent to the model that voices this witness: the
    persona and the belief *texts*. No truth flags, no distortion notes, no
    chronicle, no veils."""
    return {
        "name": w["name"],
        "role": w["role"],
        "of": w["faction_name"],
        "manner": w["manner"],
        "bias": w["bias"],
        "holds_these_beliefs": [b["text"] for b in w["beliefs"]],
        "will_not_speak_of_something": bool(w.get("veil_touched")),
    }
