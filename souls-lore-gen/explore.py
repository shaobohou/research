"""Agent-facing exploration API: the world as a discovery game.

An exploring agent is a *player*, not a reader of the repo. This module
enforces the epistemic boundary: the seeker sees only the diegetic surface
plus what it has physically reached, while the ledger's hidden layer (event
`hidden` fields, veils, false-rumor flags) stays server-side. Fog of war is
state, not model discipline; per-explorer progress persists in
worlds/seed-N/explorations/<name>.json.

Two design commitments, added to bring this closer to the Elden Ring feel:

  SPACE — you are a body somewhere. Items lie at places; you learn a place's
  items only by TRAVELLING there. `survey` shows the map you have charted,
  not a catalogue of everything. Each item's placement line ("found at the
  foot of a throne...") is its own evidence channel — the *where* is a clue.

  NO ORACLE (default) — nothing answers "from canon". `ask` and `confide`
  require a *person* standing where you stand, and that person replies from a
  bounded belief set (see witness.py) that is partly doctrine and partly
  wrong. They can endorse a falsehood they were taught and deny a truth no one
  ever told them. Ground truth is reachable from exactly one method,
  `_judge_against_truth`, used only by benchmark mode (purist=False) for eval
  harnesses — never from a seeker action.

The loop: survey (map) -> travel -> look -> examine -> talk / ask / delve ->
travel on -> confide.
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
from pathlib import Path

from ledger import (Ledger, LedgerError, ROADS_NAME, ensure_geography,
                    render_chronicle, render_codex)
from expand import expand_event
from loregen import (DEFAULT_MODEL, elaborate, witness_reaction,
                     witness_reply)
from witness import (bearing_on, ensure_witnesses, speakable,
                     witnesses_at)

DEFAULT_BUDGET = {"steps": 8, "delves": 5, "asks": 8}

VERDICTS = ["established", "consistent", "unsupported", "contradicted", "veiled"]


class Exploration:
    def __init__(self, world_dir: Path, explorer: str = "seeker",
                 role: str = "seeker", model: str = DEFAULT_MODEL,
                 purist: bool = True, budget: dict | None = None):
        self.world_dir = Path(world_dir)
        ledger_path = self.world_dir / "ledger.json"
        if not ledger_path.exists():
            raise FileNotFoundError(f"no world at {ledger_path}")
        self.lg = Ledger.load(ledger_path)
        dirty = ensure_geography(self.lg)      # migrate old ledgers in place
        dirty = ensure_witnesses(self.lg) or dirty
        if dirty:
            self.lg.save(ledger_path)
        self.explorer = explorer
        self.role = role
        self.model = model
        self.purist = purist and role != "archivist"
        self.roads_id = self.lg.find_place(ROADS_NAME)[0]
        self.state_path = self.world_dir / "explorations" / f"{explorer}.json"
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text())
            self.state.setdefault("location", self.roads_id)
            self.state.setdefault("visited", [self.roads_id])
            self.state.setdefault("known_places", self._roads_neighbours())
            self.state.setdefault("found_items", [])
            self.state["budget"].setdefault("steps", DEFAULT_BUDGET["steps"])
            # states written before budgets were configurable have no record
            # of what they started with; assume the defaults they ran under
            self.state.setdefault("start_budget", dict(DEFAULT_BUDGET))
        else:
            start = dict(DEFAULT_BUDGET)
            if budget:
                start.update(budget)
            self.state = {
                "explorer": explorer,
                "location": self.roads_id,
                "visited": [self.roads_id],
                "known_places": self._roads_neighbours(),
                "found_items": [],         # item ids whose site you've reached
                "discovered": [],          # item ids examined
                "asks": [],
                "delves": [],
                "theories": [],
                "budget": dict(start),
                "start_budget": dict(start),   # for spent-so-far reporting
            }

    # -- plumbing ---------------------------------------------------------------

    def _save_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2))

    def _save_world(self):
        ensure_geography(self.lg)
        self.lg.save(self.world_dir / "ledger.json")
        (self.world_dir / "chronicle.md").write_text(render_chronicle(self.lg))
        (self.world_dir / "codex.md").write_text(render_codex(self.lg))

    def _spend(self, kind: str) -> bool:
        if self.state["budget"].get(kind, 0) <= 0:
            return False
        self.state["budget"][kind] -= 1
        return True

    def _pname(self, pid: str) -> str:
        return self.lg.get(pid)["name"]

    # -- geography ---------------------------------------------------------------

    def _roads_neighbours(self) -> list[str]:
        """From the roads, every faction seat is reachable."""
        seats = {self.lg.find_place(k["seat"])[0]
                 for _, k in self.lg.of_type("faction")}
        seats.add(self.roads_id)
        return sorted(seats)

    def _neighbours(self, place_id: str) -> list[str]:
        """Ways onward from a place: the other places named in the events
        that happened here (the world points you along its own history),
        plus the roads, which are always regainable."""
        if place_id == self.roads_id:
            return self._roads_neighbours()
        out = {self.roads_id}
        for eid, e in self.lg.of_type("event"):
            if e.get("place") != place_id:
                continue
            # places named in this event's text, or in its parent/children
            related = [e]
            if e.get("parent"):
                related.append(self.lg.get(e["parent"]))
            related += [c for _, c in self.lg.children_of(eid)]
            for r in related:
                for pid, p in self.lg.of_type("place"):
                    if pid != place_id and p["name"] in r["text"]:
                        out.add(pid)
        out.discard(place_id)
        return sorted(out)

    def _items_at(self, place_id: str) -> list[str]:
        return [aid for aid, a in sorted(self.lg.of_type("artifact"))
                if a.get("site") == place_id]

    # -- tools: MAP & MOVEMENT ---------------------------------------------------

    def survey(self) -> dict:
        """The map you have charted: where you stand, the places you know,
        which you have walked, and your remaining strength. Not a catalogue —
        you learn what a place holds only by going there."""
        loc = self.state["location"]
        known = self.state["known_places"]
        visited = set(self.state["visited"])
        places = []
        for pid in sorted(known, key=self._pname):
            walked = pid in visited
            here = self._items_at(pid) if walked else []
            places.append({
                "place": self._pname(pid),
                "status": "here" if pid == loc else
                          ("walked" if walked else "heard of"),
                "relics_seen": len(here),
            })
        return {
            "world": f"seed-{self.lg.meta['seed']} ({self.lg.meta['archetype_key']})",
            "epigraph": self.lg.meta["epigraph"],
            "ages": [a["name"] for a in self.lg.d["ages"]],
            "you_are_at": self._pname(loc),
            "places_known": places,
            "budget": dict(self.state["budget"]),
            "hint": "travel(place) to walk somewhere you have heard of; "
                    "look() to see what lies where you stand.",
        }

    def look(self) -> dict:
        """What lies where you stand: relics here (with how each was found),
        and the ways onward."""
        loc = self.state["location"]
        here = self._items_at(loc)
        # arriving/looking reveals the names of what is here
        changed = False
        for aid in here:
            if aid not in self.state["found_items"]:
                self.state["found_items"].append(aid)
                changed = True
        relics = [{"id": aid, "name": self.lg.get(aid)["name"],
                   "type": self.lg.get(aid)["item_type"],
                   "how_it_lies": self.lg.get(aid).get("placement"),
                   "examined": aid in self.state["discovered"]}
                  for aid in here]
        onward = [self._pname(pid) for pid in self._neighbours(loc)
                  if pid != loc]
        if changed:
            self._save_state()
        return {
            "place": self._pname(loc),
            "relics_here": relics,
            "ways_onward": onward,
            "hint": "examine(name) to study a relic here; a relic's resting "
                    "place is itself a clue.",
        }

    def travel(self, place: str) -> dict:
        """Walk to a place you have heard of. New ground costs a step;
        returning to somewhere you have walked is free. Arriving reveals what
        lies there and the ways onward."""
        try:
            pid, _ = self.lg.find_place(place)
        except LedgerError:
            return {"error": f"No road you know leads to \"{place}\". "
                             "Consult your map with survey()."}
        loc = self.state["location"]
        reachable = set(self._neighbours(loc)) | set(self.state["known_places"])
        if pid not in reachable:
            return {"error": f"{self._pname(pid)} lies beyond any road you have "
                             "charted. Reach it by way of somewhere nearer."}
        new_ground = pid not in self.state["visited"]
        if new_ground and not self._spend("steps"):
            return {"error": "Your strength for the road is spent. "
                             "(step budget exhausted — you may still study "
                             "what you have found)"}
        self.state["location"] = pid
        if new_ground:
            self.state["visited"].append(pid)
        # learn the ways onward as places-heard-of
        for nb in self._neighbours(pid):
            if nb not in self.state["known_places"]:
                self.state["known_places"].append(nb)
        self._save_state()
        return {"arrived": self._pname(pid),
                "steps_left": self.state["budget"]["steps"],
                **self.look()}

    # -- tools: STUDY -------------------------------------------------------------

    def _leads(self, text: str, exclude: set[str]) -> list[dict]:
        leads, seen = [], set()
        for eid, e in self.lg.entities.items():
            if eid in exclude or e["type"] in ("event", "place"):
                continue
            nm = e.get("name")
            if nm and nm in text and nm not in seen:
                seen.add(nm)
                kind = "item" if e["type"] == "artifact" else e["type"]
                leads.append({"name": nm, "kind": kind})
        for pid, p in self.lg.of_type("place"):
            if p["name"] in text and p["name"] not in seen:
                seen.add(p["name"])
                known = pid in self.state["known_places"]
                leads.append({"name": p["name"], "kind": "place",
                              "reachable": known})
        return leads

    def examine(self, item: str) -> dict:
        """Study a relic — one you stand beside, or one you have already
        found. Returns its description, how it lies, and leads."""
        try:
            aid, a = self.lg.find_artifact(item)
        except LedgerError:
            return {"error": f"No record survives of a thing called "
                             f"\"{item}\"."}
        here = a.get("site") == self.state["location"]
        if not (here or aid in self.state["found_items"]
                or aid in self.state["discovered"]):
            return {"error": f"You have not found the {a['name']}. It lies "
                             "somewhere you have not yet walked."}
        if aid not in self.state["discovered"]:
            self.state["discovered"].append(aid)
        if aid not in self.state["found_items"]:
            self.state["found_items"].append(aid)
        self._save_state()
        desc = a["description"] or "(the entry is water-stained and unreadable)"
        return {
            "id": aid, "name": a["name"], "type": a["item_type"],
            "description": desc,
            "how_it_lies": a.get("placement"),
            "leads": self._leads(desc, exclude={aid}),
        }

    def talk(self) -> dict:
        """Who is here to be spoken to. Most who knew are dead; the living are
        inheritors, and they know only what came down to them."""
        here = witnesses_at(self.lg, self.state["location"])
        return {
            "place": self._pname(self.state["location"]),
            "people_here": [{"name": w["name"], "role": w["role"],
                             "of": w["faction_name"]} for _, w in here],
            "hint": ("ask(question) puts a question to whoever is here. They "
                     "answer from what they believe — no more, and not always "
                     "rightly."
                     if here else
                     "No one is here. The dead do not answer; find the living, "
                     "or read what they left."),
        }

    def ask(self, question: str) -> dict:
        """Put a question to a person standing here. There is no archive to
        consult: if nobody present holds anything bearing on it, you get
        nothing. Costs 1 ask (refunded when there is no one to ask)."""
        here = witnesses_at(self.lg, self.state["location"])
        if not here:
            return {"error": "There is no one here to ask. This world keeps no "
                             "archive that answers on its own."}
        if not self._spend("asks"):
            self._save_state()
            return {"error": "You have no more patience for asking today. "
                             "(ask budget spent)"}
        fid, w = here[0]
        relevant = bearing_on(self.lg, w, question)
        speech = witness_reply(speakable(w), question,
                               [b["text"] for b in relevant],
                               knows_nothing=not relevant, model=self.model)
        fragment = f"{speech}\n    — {w['name']}, {w['role']} of {w['faction_name']}"
        rid = f"frag:q{len(self.state['asks']) + 1}"
        self.state["asks"].append({"id": rid, "question": question,
                                   "fragment": fragment, "witness": w["name"]})
        self._save_state()
        return {"id": rid, "spoke_to": w["name"], "fragment": fragment,
                "asks_left": self.state["budget"]["asks"]}

    # -- delve -----------------------------------------------------------------

    def _first_unexpanded(self, roots: list[str]) -> str | None:
        queue = list(roots)
        while queue:
            eid = queue.pop(0)
            if not self.lg.get(eid)["expanded"]:
                return eid
            queue.extend(cid for cid, _ in self.lg.children_of(eid))
        return None

    def _resolve_delve(self, target: str) -> str | None:
        t = target.strip()
        if re.fullmatch(r"e\d+", t) and t in self.lg.entities:
            return self._first_unexpanded([t])
        try:
            _, a = self.lg.find_artifact(t)
            return self._first_unexpanded(list(reversed(a["provenance"])))
        except LedgerError:
            pass
        tl = t.lower()
        for fid, f in self.lg.of_type("figure"):
            if f["name"].lower() in tl or tl in f["name"].lower():
                # events they acted in, or that are about them
                roots = [eid for eid, e in self.lg.of_type("event")
                         if fid in e["participants"]
                         or fid in e.get("referents", [])]
                roots.sort(key=lambda eid: self.lg.get(eid)["year"])
                return self._first_unexpanded(roots)
        # place / faction: events located there or naming it
        for pid, p in self.lg.of_type("place"):
            if p["name"].lower() == tl or tl in p["name"].lower():
                roots = [eid for eid, e in self.lg.of_type("event")
                         if e.get("place") == pid or p["name"] in e["text"]]
                roots.sort(key=lambda eid: self.lg.get(eid)["year"])
                return self._first_unexpanded(roots)
        for _, k in self.lg.of_type("faction"):
            if k["name"].lower() in tl or tl in k["name"].lower():
                roots = [eid for eid, e in self.lg.of_type("event")
                         if k["name"] in e["text"]]
                roots.sort(key=lambda eid: self.lg.get(eid)["year"])
                return self._first_unexpanded(roots)
        return None

    def delve(self, target: str) -> dict:
        """Dig into a lead (item, figure, faction, place, or event id).
        Materializes deeper history behind it: new accounts, sometimes new
        relics — and any new ground they name is added to your map."""
        if not self._spend("delves"):
            self._save_state()
            return {"error": "The lanterns are spent; no more delving today. "
                             "(delve budget spent)"}
        node = self._resolve_delve(target)
        if node is None:
            self.state["budget"]["delves"] += 1
            self._save_state()
            return {"error": f"The trail of \"{target}\" leads nowhere the "
                             "records reach — or it has been dug bare already."}
        try:
            child_ids, item_ids = expand_event(self.lg, node)
        except LedgerError as e:
            self.state["budget"]["delves"] += 1
            self._save_state()
            return {"error": f"The dig collapses before it begins: {e}"}

        elaborate(self.lg, node, child_ids, item_ids, self.model)
        self._save_world()

        findings, new_places = [], []
        for cid in child_ids:
            c = self.lg.get(cid)
            findings.append({"id": f"frag:{cid}", "year": c["year"],
                             "account": c["text"]})
            pid = c.get("place")
            if pid and pid not in self.state["known_places"]:
                self.state["known_places"].append(pid)
                new_places.append(self._pname(pid))
        new_items = []
        for aid in item_ids:
            a = self.lg.get(aid)
            new_items.append({"id": aid, "name": a["name"],
                              "type": a["item_type"],
                              "lies_at": self._pname(a["site"]) if a.get("site") else None})
            if a.get("site") and a["site"] not in self.state["known_places"]:
                self.state["known_places"].append(a["site"])
                new_places.append(self._pname(a["site"]))
        self.state["delves"].append(
            {"target": target, "node": node,
             "found": [f["id"] for f in findings] + [i["id"] for i in new_items]})
        self._save_state()
        return {"findings": findings, "new_items": new_items,
                "new_ground": sorted(set(new_places)),
                "delves_left": self.state["budget"]["delves"],
                "note": "New relics lie where the accounts place them — travel "
                        "there to recover them."}

    # -- confide: a person's reaction, measured against their own beliefs ------

    _JUDGE_SCHEMA = {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "verdict": {"type": "string", "enum": VERDICTS},
                        "note": {"type": "string"},
                    },
                    "required": ["claim", "verdict", "note"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["verdicts"],
        "additionalProperties": False,
    }

    def _judge_against_truth(self, claims: list[str]) -> list[dict]:
        """BENCHMARK ONLY. This is the one place ground truth is consulted, and
        it is unreachable from any seeker action — an eval harness is allowed
        to be omniscient; a player's interlocutor is not."""
        from loregen import _stream_json, _veil_block
        discovered = [self.lg.get(aid) for aid in self.state["discovered"]]
        user = (
            "You grade a seeker's reconstruction of a hidden history.\n"
            "- established: true, and their discovered material supports it\n"
            "- consistent: true, but they have no evidence yet\n"
            "- unsupported: canon is silent\n"
            "- contradicted: false per canon\n"
            "- veiled: touches a veil\n\n"
            "=== TRUE CHRONICLE ===\n" + render_chronicle(self.lg) + "\n"
            "=== VEILS ===\n" + _veil_block(self.lg) + "\n"
            "=== WHAT THEY HAVE FOUND ===\n" +
            json.dumps([{"name": d["name"], "description": d["description"]}
                        for d in discovered], indent=2) + "\n\n"
            "=== CLAIMS ===\n" + json.dumps(claims, indent=2))
        data = _stream_json(self.model, "You grade precisely and reveal nothing.",
                            user, self._JUDGE_SCHEMA)
        return [v for v in data["verdicts"] if v["verdict"] in VERDICTS]

    def confide(self, claims: list[str]) -> dict:
        """Tell someone here what you think happened. They answer from their
        own beliefs — so they may endorse a thing they were taught wrongly and
        flatly deny a truth no one ever told them. There is no verdict, no
        score, and no one in this world who can confirm you."""
        claims = [c for c in claims if c.strip()][:12]
        if not claims:
            return {"error": "You have said nothing."}
        here = witnesses_at(self.lg, self.state["location"])
        if not here:
            return {"error": "There is no one here to tell. A theory told to "
                             "no one is just weather."}
        fid, w = here[0]
        out = witness_reaction(speakable(w), claims, model=self.model)
        self.state["theories"].append(
            {"claims": claims, "heard_by": w["name"],
             "reactions": out["reactions"], "closing": out["closing"]})
        self._save_state()
        return {"spoke_to": f"{w['name']}, {w['role']} of {w['faction_name']}",
                "reactions": out["reactions"], "closing": out["closing"],
                "note": "One person's reading, from what they happen to "
                        "believe. It is not a verdict, and they may be wrong."}

    def theorize(self, claims: list[str]) -> dict:
        """Purist (default): identical to `confide` — your theory goes to a
        person, never to an oracle. Benchmark mode grades against ground truth
        for eval harnesses only."""
        if self.purist:
            return self.confide(claims)
        claims = [c for c in claims if c.strip()][:12]
        if not claims:
            return {"error": "no claims"}
        verdicts = self._judge_against_truth(claims)
        score = sum({"established": 3, "consistent": 2, "veiled": 1,
                     "unsupported": 0, "contradicted": -1}[v["verdict"]]
                    for v in verdicts)
        self.state["theories"].append({"claims": claims, "verdicts": verdicts,
                                       "score": score})
        self._save_state()
        return {"verdicts": verdicts, "score": score}

    # -- meta ---------------------------------------------------------------------

    def progress(self) -> dict:
        n_items = len(self.lg.of_type("artifact"))
        n_places = len(self.lg.of_type("place"))
        p = {
            "explorer": self.explorer,
            "at": self._pname(self.state["location"]),
            "places_walked": f"{len(self.state['visited'])}/{n_places}",
            "relics_found": f"{len(self.state['found_items'])}/{n_items}",
            "relics_examined": f"{len(self.state['discovered'])}/{n_items}",
            "steps_left": self.state["budget"]["steps"],
            "asks_left": self.state["budget"]["asks"],
            "delves_left": self.state["budget"]["delves"],
            "theories_submitted": len(self.state["theories"]),
        }
        if not self.purist:
            p["best_theory_score"] = max(
                (t["score"] for t in self.state["theories"]), default=None)
        return p

    def canon(self) -> dict:
        if self.role != "archivist":
            return {"error": "The inner archive is barred to seekers."}
        return self.lg.d

    def compendium(self) -> str:
        """Everything this explorer has discovered, as one in-world document.
        Rendered from exploration state + public surfaces only — seeker-safe."""
        m, st = self.lg.meta, self.state
        lines = ["# The Book of Found Things", "",
                 f"*World seed-{m['seed']} ({m['archetype_key']}), as uncovered "
                 f"by the seeker \"{self.explorer}\".*", ""]
        if m["epigraph"]:
            lines += [f"> {m['epigraph']}", ""]
        b = st["budget"]
        start = st.get("start_budget", DEFAULT_BUDGET)
        spent = lambda k: start[k] - b[k]
        lines += [f"*Places walked: {len(st['visited'])} — relics examined: "
                  f"{len(st['discovered'])} — steps {spent('steps')}/"
                  f"{start['steps']}, asks {spent('asks')}/"
                  f"{start['asks']}, delves {spent('delves')}/"
                  f"{start['delves']}*", ""]

        walked = [pid for pid in st["visited"]]
        if walked:
            lines += ["## Roads Walked", ""]
            for pid in sorted(walked, key=self._pname):
                here = [self.lg.get(a) for a in self._items_at(pid)
                        if a in st["discovered"]]
                lines += [f"### {self._pname(pid)}", ""]
                if here:
                    for a in here:
                        lines += [f"- **{a['name']}** — *{a.get('placement','')}*"]
                else:
                    lines += ["- (walked, nothing studied here)"]
                lines += [""]

        if st["discovered"]:
            lines += ["## Relics Examined", ""]
            by_type: dict[str, list[dict]] = {}
            for aid in st["discovered"]:
                a = self.lg.get(aid)
                by_type.setdefault(a["item_type"], []).append(a)
            for itype in sorted(by_type):
                title = itype.title() + ("" if itype.endswith("s") else "s")
                lines += [f"### {title}", ""]
                for a in sorted(by_type[itype], key=lambda x: x["created_year"]):
                    lines += [f"**{a['name']}**", "",
                              a["description"] or "(unreadable)", ""]
                    if a.get("placement"):
                        lines += [f"*{a['placement']}*", ""]

        if st["delves"]:
            lines += ["## Accounts Unearthed", ""]
            for d in st["delves"]:
                lines += [f"### On the trail of {d['target']}", ""]
                for fid in d["found"]:
                    if fid.startswith("frag:"):
                        e = self.lg.get(fid.split(":", 1)[1])
                        lines += [f"- *(year {e['year']}, {e['kind']})* {e['text']}"]
                    else:
                        a = self.lg.get(fid)
                        lines += [f"- **Brought back:** {a['name']} ({a['item_type']})"]
                lines += [""]

        if st["asks"]:
            lines += ["## Words of the Archives", ""]
            for a in st["asks"]:
                lines += [f"**{a['question']}**", "",
                          "> " + a["fragment"].replace("\n", "\n> "), ""]

        if st["theories"]:
            lines += ["## Theories Ventured", ""]
            for i, t in enumerate(st["theories"], 1):
                lines += [f"### Theory {i}", ""]
                for c in t["claims"]:
                    lines += [f"- {c}"]
                lines += [""]

        unfound = [a["name"] for aid, a in sorted(self.lg.of_type("artifact"))
                   if aid not in st["found_items"]]
        lines += ["## Beyond the Charted Roads", ""]
        if unfound:
            lines += [f"{len(unfound)} relics remain somewhere unwalked, their "
                      "names not yet even known to you.", ""]
        lines += [f"Strength remaining: {b['steps']} steps, {b['delves']} "
                  f"delves, {b['asks']} asks. The rest of the world keeps its "
                  "counsel.", ""]
        return "\n".join(lines)
