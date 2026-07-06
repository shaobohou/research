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

from worldsim import World


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
                "participants": e.participants,
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
                  depth: int, source: str) -> str:
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
        eid = self.next_id("e")
        self.entities[eid] = {
            "type": "event", "kind": kind, "year": year, "text": text,
            "hidden": hidden, "participants": participants,
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
        lines.append(f"{pad}- **Year {e['year']}** — *{e['kind']}*: {e['text']}")
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
            lines.append("")
    return "\n".join(lines)
