"""The canon ledger: a persistent, append-only fact store for one world.

Everything the sim or the LLM ever asserts about a world lands here as an
entity record or a note. Once written, a fact is an invariant: later
expansions and elaborations are validated against it. The ledger is the
single source of truth — chronicle and codex are both rendered from it.

Layout (worlds/seed-N/ledger.json):
    meta      seed, archetype fields, veils, epigraph, counters, used names
    ages      [{name, start, end, blurb}]
    entities  {id: record}   figure | faction | event | artifact
    notes     [{entity_id, text, source}]   free-text texture facts
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from worldsim import PLACE_SUFFIXES, World


class LedgerError(ValueError):
    """A proposed fact contradicts established canon."""


class Ledger:
    def __init__(self, data: dict):
        self.d = data

    # -- construction --------------------------------------------------------

    @classmethod
    def from_world(cls, w: World) -> "Ledger":
        entities: dict[str, dict] = {}
        for f in w.figures:
            entities[f.id] = {
                "type": "figure", "name": f.name, "epithet": f.epithet,
                "role": f.role, "faction": f.faction_id, "is_god": f.is_god,
                "fate": f.fate, "fate_year": f.fate_year,
                "depth": 0, "source": "sim",
            }
        for k in w.factions:
            entities[k.id] = {
                "type": "faction", "name": k.name, "kind": k.kind,
                "seat": k.seat, "founded_year": k.founded_year,
                "founder": k.founder_id, "fallen_year": k.fallen_year,
                "depth": 0, "source": "sim",
            }
        for e in w.events:
            entities[e.id] = {
                "type": "event", "kind": e.kind, "year": e.year,
                "text": e.text, "hidden": e.hidden,
                "participants": e.participants, "referents": e.referents,
                "damages": e.damages,
                "parent": None, "depth": 0, "expanded": False, "source": "sim",
            }
        for a in w.artifacts:
            entities[a.id] = {
                "type": "artifact", "name": a.name, "item_type": a.item_type,
                "created_year": a.created_year,
                "origin_faction": a.origin_faction_id,
                "provenance": a.provenance, "knowledge": a.knowledge,
                "bias": a.bias, "false_rumor": a.false_rumor,
                "hints_veil": 0 if a.hints_mystery else None,
                "description": None, "depth": 0, "source": "sim",
            }
        arch = w.archetype
        data = {
            "meta": {
                "seed": w.seed,
                "archetype_key": w.archetype_key,
                "primordial": w.primordial_name,
                "gift": arch["gift"],
                "waning": arch["waning"],
                "curse_name": arch["curse_name"],
                "curse_desc": arch["curse_desc"],
                "relic_nouns": arch["relic_nouns"],
                "veils": w.veils,
                "epigraph": None,
                "present_year": max(e.year for e in w.events),
                "used_names": w.used_names,
            },
            "ages": [{"name": a.name, "start": a.start, "end": a.end,
                      "blurb": a.blurb} for a in w.ages],
            "entities": entities,
            "notes": [],
        }
        return cls(data)

    @classmethod
    def load(cls, path: Path) -> "Ledger":
        return cls(json.loads(path.read_text()))

    def save(self, path: Path):
        path.write_text(json.dumps(self.d, indent=2))

    # -- accessors ------------------------------------------------------------

    @property
    def meta(self) -> dict:
        return self.d["meta"]

    @property
    def entities(self) -> dict[str, dict]:
        return self.d["entities"]

    def get(self, eid: str) -> dict:
        try:
            return self.entities[eid]
        except KeyError:
            raise LedgerError(f"unknown entity id: {eid}")

    def of_type(self, t: str) -> list[tuple[str, dict]]:
        return [(i, e) for i, e in self.entities.items() if e["type"] == t]

    def children_of(self, eid: str) -> list[tuple[str, dict]]:
        kids = [(i, e) for i, e in self.of_type("event") if e.get("parent") == eid]
        return sorted(kids, key=lambda p: p[1]["year"])

    def notes_for(self, eid: str) -> list[str]:
        return [n["text"] for n in self.d["notes"] if n["entity_id"] == eid]

    def next_id(self, prefix: str) -> str:
        best = 0
        for eid in self.entities:
            m = re.fullmatch(rf"{prefix}(\d+)", eid)
            if m:
                best = max(best, int(m.group(1)))
        return f"{prefix}{best + 1}"

    def find_place(self, needle: str) -> tuple[str, dict]:
        needle = needle.lower()
        hits = [(i, e) for i, e in self.of_type("place")
                if needle in e["name"].lower()]
        if not hits:
            raise LedgerError(f"no place matching {needle!r}")
        hits.sort(key=lambda p: len(p[1]["name"]))
        return hits[0]

    def find_artifact(self, needle: str) -> tuple[str, dict]:
        needle = needle.lower()
        hits = [(i, e) for i, e in self.of_type("artifact")
                if needle in e["name"].lower()]
        if not hits:
            raise LedgerError(f"no artifact matching {needle!r}")
        if len(hits) > 1:
            names = ", ".join(e["name"] for _, e in hits)
            raise LedgerError(f"ambiguous item {needle!r}: {names}")
        return hits[0]

    # -- validated mutation ----------------------------------------------------

    def _claim_name(self, name: str):
        if name in self.meta["used_names"]:
            raise LedgerError(f"name already in use: {name}")
        self.meta["used_names"].append(name)

    def add_figure(self, name: str, epithet: str, role: str,
                   faction: str | None, depth: int, source: str) -> str:
        self._claim_name(name)
        if faction is not None:
            self.get(faction)
        fid = self.next_id("f")
        self.entities[fid] = {
            "type": "figure", "name": name, "epithet": epithet, "role": role,
            "faction": faction, "is_god": False, "fate": None,
            "fate_year": None, "depth": depth, "source": source,
        }
        return fid

    def add_event(self, kind: str, year: int, text: str, hidden: str | None,
                  participants: list[str], parent: str | None,
                  depth: int, source: str,
                  referents: list[str] | None = None) -> str:
        if not (0 <= year <= self.meta["present_year"]):
            raise LedgerError(
                f"event year {year} outside [0, {self.meta['present_year']}]")
        for pid in participants:
            p = self.get(pid)
            if p["type"] != "figure":
                raise LedgerError(f"participant {pid} is not a figure")
            if p["fate_year"] is not None and year > p["fate_year"]:
                raise LedgerError(
                    f"{p['name']} cannot act in year {year}: "
                    f"fate ({p['fate']}) sealed in year {p['fate_year']}")
        if parent is not None and self.get(parent)["type"] != "event":
            raise LedgerError(f"parent {parent} is not an event")
        for rid in referents or []:
            if self.get(rid)["type"] != "figure":
                raise LedgerError(f"referent {rid} is not a figure")
        eid = self.next_id("e")
        self.entities[eid] = {
            "type": "event", "kind": kind, "year": year, "text": text,
            "hidden": hidden, "participants": participants,
            "referents": list(referents or []),
            "parent": parent, "depth": depth, "expanded": False,
            "source": source,
        }
        return eid

    def add_artifact(self, name: str, item_type: str, created_year: int,
                     origin_faction: str | None, provenance: list[str],
                     knowledge: list[str], bias: str, false_rumor: str | None,
                     hints_veil: int | None, depth: int, source: str) -> str:
        self._claim_name(name)
        for eid in provenance:
            if self.get(eid)["type"] != "event":
                raise LedgerError(f"provenance {eid} is not an event")
        aid = self.next_id("a")
        self.entities[aid] = {
            "type": "artifact", "name": name, "item_type": item_type,
            "created_year": created_year, "origin_faction": origin_faction,
            "provenance": provenance, "knowledge": knowledge, "bias": bias,
            "false_rumor": false_rumor, "hints_veil": hints_veil,
            "description": None, "depth": depth, "source": source,
        }
        return aid

    def add_note(self, entity_id: str, text: str, source: str):
        self.get(entity_id)
        self.d["notes"].append(
            {"entity_id": entity_id, "text": text, "source": source})

    # -- subgraph for prompts ----------------------------------------------------

    def subgraph(self, eids: list[str]) -> dict:
        """Entity records (plus one hop of links) relevant to a prompt."""
        wanted: set[str] = set(eids)
        for eid in list(wanted):
            e = self.get(eid)
            wanted.update(e.get("participants", []))
            wanted.update(e.get("referents", []))
            wanted.update(e.get("provenance", []))
            for key in ("faction", "origin_faction", "parent", "founder"):
                if e.get(key):
                    wanted.add(e[key])
        out = {}
        for eid in sorted(wanted):
            rec = dict(self.get(eid))
            notes = self.notes_for(eid)
            if notes:
                rec["notes"] = notes
            out[eid] = rec
        return out


# ---------------------------------------------------------------------------
# Geography: places, event locations, item placement
# ---------------------------------------------------------------------------
# Derived rather than simulated: place names already live inside event texts
# (they come from the same Namer), so geography can be reconstructed for any
# ledger — including pre-geography ones — deterministically and idempotently.

ROADS_NAME = "the Pilgrim Roads"

# Placement lines are an EVIDENCE channel, so they are sim-controlled (like
# knowledge packets), never free prose: derived from where an item's story
# ended. Keyed by the kind of the last provenance event, with item-type
# fallbacks.
_PLACEMENT_BY_KIND = {
    "fall of a kingdom": "Found at the foot of a throne in {place}, beneath the dust of the banners.",
    "hero's end": "Left behind at {place}, and never reclaimed.",
    "sealing": "Worn smooth by warders' hands at {place}.",
    "the paying of the price": "Set among the grave-offerings at {place}; the offerings were counted, once.",
    "the wardens' charge": "Passed down at {place}, hand to reluctant hand.",
    "betrayal": "Recovered from a gatehouse at {place} that no one will garrison again.",
    "the price named": "Found sewn into a courier's coat on the roads out of {place}.",
    "rite of restoration": "Kept in a reliquary at {place}, before which the candles will not stay lit.",
    "the procession": "Dropped along the procession road near {place}, and left where it fell.",
    "the choosing": "Found in an empty cell at {place}, the door unlocked.",
    "twilight of a god": "Taken from a throne room at {place} where nothing else was disturbed.",
    "the empty seat": "Taken from a throne room at {place} where nothing else was disturbed.",
    "great war": "Dug from the old battle-earth near {place}.",
    "battle": "Dug from the old battle-earth near {place}.",
    "champion's duel": "Found on the dueling ground at {place}, laid down rather than dropped.",
    "the seal weakens": "Confiscated from pilgrims on the roads to {place}.",
    "last pilgrimage": "Recovered from a wayside camp on the road to {place}, struck in haste.",
    "forging": "Kept long at {place}, and then kept poorly.",
    "founding": "Displayed at {place} until display became burial.",
}

_PLACEMENT_BY_TYPE = {
    "weapon": "Found driven upright in the earth near {place}.",
    "armor": "Found arranged, empty, at {place} — as if for a burial without a body.",
    "ring": "Pried from a hand at {place}; the hand did not object.",
    "talisman": "Left upon a roadside shrine near {place}.",
    "soul remnant": "Lingers at {place}, where it was loosed.",
    "key item": "Found where it was abandoned, at {place}.",
    "consumable": "Bought from a peddler working the roads near {place}.",
    "catalyst": "Recovered from a scholar's cell at {place}, its door locked from within.",
}


def ensure_geography(lg: Ledger) -> bool:
    """Create place entities, locate events, and place items. Idempotent;
    returns True if the ledger changed. Safe to run on old ledgers and after
    every expansion (fills only missing fields)."""
    changed = False
    places: dict[str, str] = {e["name"]: pid for pid, e in lg.of_type("place")}
    suffix_re = re.compile(
        r"\b([A-Z][a-z]+(?:" + "|".join(PLACE_SUFFIXES) + r"))\b")

    # Person-name endings overlap PLACE_SUFFIXES (e.g. "-mere"), so a bare
    # regex sweep of event text would mint phantom places named after people.
    # Realm names legitimately double as places (a fallen kingdom is somewhere
    # you can stand), but that aliasing is recorded, not accidental.
    figure_names = {f["name"] for _, f in lg.of_type("figure")}
    faction_names = {k["name"]: kid for kid, k in lg.of_type("faction")}

    def ensure_place(name: str) -> str:
        nonlocal changed
        if name in places:
            return places[name]
        pid = lg.next_id("p")
        rec = {"type": "place", "name": name, "source": "geo"}
        if name in faction_names:
            rec["aka_faction"] = faction_names[name]
        lg.entities[pid] = rec
        if name not in lg.meta["used_names"]:
            lg.meta["used_names"].append(name)
        places[name] = pid
        changed = True
        return pid

    roads = ensure_place(ROADS_NAME)
    for _, k in lg.of_type("faction"):
        ensure_place(k["seat"])

    for eid, e in lg.of_type("event"):
        mentioned = [nm for nm in suffix_re.findall(e["text"])
                     if nm not in figure_names]
        for nm in mentioned:
            ensure_place(nm)
        if e.get("place") is None:
            pid = places[mentioned[0]] if mentioned else None
            if pid is None:
                for fid in e["participants"]:
                    fac = lg.get(fid).get("faction")
                    if fac:
                        pid = places[lg.get(fac)["seat"]]
                        break
            e["place"] = pid or roads
            changed = True

    for aid, a in lg.of_type("artifact"):
        if a.get("site") is None:
            if a["provenance"]:
                a["site"] = lg.get(a["provenance"][-1])["place"]
            elif a["origin_faction"]:
                a["site"] = places[lg.get(a["origin_faction"])["seat"]]
            else:
                a["site"] = roads
            changed = True
        if a.get("placement") is None:      # fill independently of site so
            kind = (lg.get(a["provenance"][-1])["kind"]   # expansion-set sites
                    if a["provenance"] else None)         # keep their own site
            tpl = _PLACEMENT_BY_KIND.get(kind) or _PLACEMENT_BY_TYPE.get(
                a["item_type"], "Found upon the roads near {place}.")
            a["placement"] = tpl.format(place=lg.get(a["site"])["name"])
            changed = True
    return changed


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_chronicle(lg: Ledger) -> str:
    m = lg.meta
    lines: list[str] = [f"# The True Chronicle (seed {m['seed']})", ""]
    lines.append("> **Spoilers.** This is the ground truth the items only hint at.")
    lines.append("")
    lines.append(f"**Cosmology:** {m['primordial']} — gift of {m['gift']}.")
    lines.append(f"**The waning:** {m['waning']}.")
    lines.append(f"**The curse:** {m['curse_name']} — {m['curse_desc']}.")
    lines.append("")
    lines.append("**THE VEILS (each partially true, reframed by the next; "
                 "never stated by any item):**")
    for i, v in enumerate(m["veils"]):
        lines.append(f"{i + 1}. {v}")
    lines.append("")

    lines.append("## Ages")
    for a in lg.d["ages"]:
        end = a["end"] if a["end"] is not None else "present"
        lines.append(f"- **{a['name']}** (years {a['start']}–{end}): {a['blurb']}")
    lines.append("")

    lines.append("## Timeline")

    def emit(eid: str, e: dict, indent: int):
        pad = "  " * indent
        at = ""
        if e.get("place"):
            at = f" _(at {lg.get(e['place'])['name']})_"
        lines.append(f"{pad}- **Year {e['year']}** — *{e['kind']}*: {e['text']}{at}")
        if e["hidden"]:
            lines.append(f"{pad}  - _Hidden:_ {e['hidden']}")
        for nt in lg.notes_for(eid):
            lines.append(f"{pad}  - _Note:_ {nt}")
        for cid, c in lg.children_of(eid):
            emit(cid, c, indent + 1)

    roots = sorted((p for p in lg.of_type("event") if p[1]["parent"] is None),
                   key=lambda p: p[1]["year"])
    for eid, e in roots:
        emit(eid, e, 0)
    lines.append("")

    lines.append("## Dramatis Personae")
    for fid, f in lg.of_type("figure"):
        fac = f" — of {lg.get(f['faction'])['name']}" if f["faction"] else ""
        fate = f" Fate: {f['fate']} (year {f['fate_year']})." if f["fate"] else ""
        god = " [god]" if f["is_god"] else ""
        lines.append(f"- **{f['name']}** {f['epithet']}{god} ({f['role']}){fac}.{fate}")
        for nt in lg.notes_for(fid):
            lines.append(f"  - _Note:_ {nt}")
    lines.append("")

    lines.append("## Factions")
    for kid, k in lg.of_type("faction"):
        fallen = f", fell year {k['fallen_year']}" if k["fallen_year"] else ""
        lines.append(f"- **{k['name']}** ({k['kind']}), seat {k['seat']}, "
                     f"founded year {k['founded_year']}{fallen}.")
        for nt in lg.notes_for(kid):
            lines.append(f"  - _Note:_ {nt}")
    lines.append("")

    places = lg.of_type("place")
    if places:
        lines.append("## Places")
        for pid, p in places:
            items_here = [a["name"] for _, a in lg.of_type("artifact")
                          if a.get("site") == pid]
            held = f" — holds {', '.join(items_here)}" if items_here else ""
            lines.append(f"- **{p['name']}**{held}.")
        lines.append("")
    return "\n".join(lines)


def render_codex(lg: Ledger) -> str:
    m = lg.meta
    lines = [f"# Codex of Found Things (seed {m['seed']})", ""]
    if m["epigraph"]:
        lines.append(f"*{m['epigraph']}*")
        lines.append("")
    by_type: dict[str, list[dict]] = {}
    for _, a in lg.of_type("artifact"):
        by_type.setdefault(a["item_type"], []).append(a)
    for itype in sorted(by_type):
        title = itype.title() if itype.endswith("s") else itype.title() + "s"
        lines.append(f"## {title}")
        lines.append("")
        for a in sorted(by_type[itype], key=lambda x: x["created_year"]):
            lines.append(f"### {a['name']}")
            lines.append("")
            lines.append(a["description"] or "(no description generated)")
            if a.get("placement"):
                lines.append("")
                lines.append(f"*{a['placement']}*")
            lines.append("")
    return "\n".join(lines)
