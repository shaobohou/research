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

  PURIST MODE (default) — the world never tells you that you are right.
  `theorize` returns an in-world RECEPTION (a rival antiquary's reaction),
  never a verdict. Touch a veil and they go cold — which is itself the only
  confirmation you will ever get. A separate benchmark mode (purist=False,
  used by eval harnesses) restores machine verdicts; seekers never see them.

The loop: survey (map) -> travel -> look -> examine -> ask / delve ->
travel on -> theorize.
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
from loregen import ask_world, elaborate

DEFAULT_BUDGET = {"steps": 8, "delves": 5, "asks": 8}

VERDICTS = ["established", "consistent", "unsupported", "contradicted", "veiled"]


def _llm_guard(fn, *args, fallback):
    """Run an LLM path; fall back to templates when no key is configured."""
    try:
        return fn(*args)
    except Exception as e:
        if os.environ.get("ANTHROPIC_API_KEY"):
            raise
        print(f"LLM call failed ({type(e).__name__}); template mode.",
              file=sys.stderr)
        return fallback()


class Exploration:
    def __init__(self, world_dir: Path, explorer: str = "seeker",
                 role: str = "seeker", model: str | None = None,
                 purist: bool = True, budget: dict | None = None):
        self.world_dir = Path(world_dir)
        ledger_path = self.world_dir / "ledger.json"
        if not ledger_path.exists():
            raise FileNotFoundError(f"no world at {ledger_path}")
        self.lg = Ledger.load(ledger_path)
        if ensure_geography(self.lg):          # migrate old ledgers in place
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

    def ask(self, question: str) -> dict:
        """Ask the archives; answered in-world, from canon, never the veils."""
        if not self._spend("asks"):
            self._save_state()
            return {"error": "The archivists will hear no more questions "
                             "today. (ask budget spent)"}
        fragment = _llm_guard(
            ask_world, self.lg, question, self.model,
            fallback=lambda: ask_world(self.lg, question, None))
        fid = f"frag:q{len(self.state['asks']) + 1}"
        self.state["asks"].append({"id": fid, "question": question,
                                   "fragment": fragment})
        self._save_state()
        return {"id": fid, "fragment": fragment,
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

        _llm_guard(
            elaborate, self.lg, node, child_ids, item_ids, self.model,
            fallback=lambda: elaborate(self.lg, node, child_ids, item_ids, None))
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

    # -- theorize: purist reception vs benchmark verdicts ------------------------

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

    def _judge_llm(self, claims: list[str]) -> list[dict]:
        from loregen import _stream_json, _veil_block
        discovered = [self.lg.get(aid) for aid in self.state["discovered"]]
        found_frags = list(self.state["asks"]) + self.state["delves"]
        user = (
            "You are the hidden judge of a lore-discovery game. Grade each "
            "claim against the TRUE chronicle:\n"
            "- established: true, AND the seeker's discovered material supports it\n"
            "- consistent: true in canon, but the seeker has no evidence yet\n"
            "- unsupported: canon is silent either way\n"
            "- contradicted: false per canon\n"
            "- veiled: the claim touches a veil (right or wrong)\n"
            "The note must be one in-world sentence that reveals nothing the "
            "seeker hasn't found and never states a veil.\n\n"
            "=== TRUE CHRONICLE ===\n" + render_chronicle(self.lg) + "\n"
            "=== VEILS ===\n" + _veil_block(self.lg) + "\n"
            "=== SEEKER'S DISCOVERED MATERIAL ===\n" +
            json.dumps({"examined_items": [{"name": d["name"],
                                            "description": d["description"]}
                                           for d in discovered],
                        "fragments": found_frags}, indent=2) + "\n\n"
            "=== CLAIMS ===\n" + json.dumps(claims, indent=2))
        data = _stream_json(self.model, "You grade precisely and reveal nothing.",
                            user, self._JUDGE_SCHEMA)
        return [v for v in data["verdicts"] if v["verdict"] in VERDICTS]

    def _judge_lexical(self, claims: list[str]) -> list[dict]:
        def words(s: str) -> set[str]:
            return {w.strip(".,;:—\"'()").lower() for w in s.split()
                    if len(w) > 3}
        canon_texts = []
        for eid, e in self.lg.of_type("event"):
            canon_texts.append(e["text"])
            if e["hidden"]:
                canon_texts.append(e["hidden"])
        canon_texts += [n["text"] for n in self.lg.d["notes"]]
        discovered_words = words(" ".join(
            (self.lg.get(aid)["description"] or "")
            for aid in self.state["discovered"]))
        out = []
        for claim in claims:
            cw = words(claim)
            if not cw:
                out.append({"claim": claim, "verdict": "unsupported",
                            "note": "The archivists cannot parse silence."})
                continue
            veil_hit = max((len(cw & words(v)) / len(cw)
                            for v in self.lg.meta["veils"]), default=0)
            best = max((len(cw & words(t)) / len(cw) for t in canon_texts),
                       default=0)
            if veil_hit >= 0.35 and veil_hit >= best:
                v, note = "veiled", "Here the archives go quiet."
            elif best >= 0.5:
                if len(cw & discovered_words) / len(cw) >= 0.4:
                    v, note = "established", "The records you hold bear this out."
                else:
                    v, note = "consistent", ("Nothing you have found says so — "
                                             "but nothing denies it.")
            else:
                v, note = "unsupported", "No surviving record speaks to this."
            out.append({"claim": claim, "verdict": v, "note": note})
        return out

    def _graded(self, claims: list[str]) -> list[dict]:
        if self.model is None:
            return self._judge_lexical(claims)
        return _llm_guard(self._judge_llm, claims,
                          fallback=lambda: self._judge_lexical(claims))

    # in-world reactions, keyed by the true verdict but NEVER exposing it.
    # Purist: the seeker gets a fellow antiquary's response, not a score.
    _RECEPTION = {
        "established": [
            "The antiquary nods slowly. \"Aye. The stones I have read say the same.\"",
            "\"This much I will grant you — it agrees with what the old things remember.\"",
        ],
        "consistent": [
            "\"It could be so. I have found nothing to forbid it — and nothing to swear by.\"",
            "The antiquary tilts a hand, palm up. \"Plausible. Bring me a stone that says it.\"",
        ],
        "unsupported": [
            "\"On what? I have read no record that carries this. You reach past your evidence.\"",
            "The antiquary frowns. \"A pretty guess with nothing under it.\"",
        ],
        "contradicted": [
            "\"No. The tellings I trust run otherwise; I would set this one down.\"",
            "The antiquary shakes their head. \"That is not the story the relics tell me.\"",
        ],
        "veiled": [
            "The antiquary goes still, and will not meet your eye. \"Speak no further on this. Some doors are shut for cause.\"",
            "A long silence. \"You should not have said that aloud. Ask me something else.\"",
        ],
    }

    def _reception(self, claims: list[str]) -> dict:
        graded = self._graded(claims)
        rng = random.Random(f"{self.lg.meta['seed']}:{self.explorer}:"
                            f"{len(self.state['theories'])}")
        reactions = []
        touched_veil = False
        for g in graded:
            pool = self._RECEPTION[g["verdict"]]
            reactions.append({"claim": g["claim"],
                              "reception": rng.choice(pool)})
            if g["verdict"] == "veiled":
                touched_veil = True
        if touched_veil:
            closing = ("The antiquary rises. \"Enough for tonight. You wander "
                       "toward things better left buried.\"")
        else:
            warm = sum(1 for g in graded
                       if g["verdict"] in ("established", "consistent"))
            if warm >= max(1, len(graded) * 2 // 3):
                closing = ("\"You have walked far and read closely. Keep on — "
                           "but the deepest of it, no scholar will confirm for you.\"")
            else:
                closing = ("\"Come back when you have found more than you have "
                           "guessed. The relics do not reward haste.\"")
        # store the true grading server-side (for later benchmark/replay),
        # expose only the reception.
        self.state["theories"].append(
            {"claims": claims, "verdicts": graded,
             "score": sum({"established": 3, "consistent": 2, "veiled": 1,
                           "unsupported": 0, "contradicted": -1}[g["verdict"]]
                          for g in graded)})
        self._save_state()
        return {"reception": reactions, "closing": closing,
                "note": "This is one antiquary's reading, not a verdict. "
                        "No one in this world will tell you that you are right."}

    def theorize(self, claims: list[str]) -> dict:
        """Lay your theory before a fellow antiquary. In purist mode (the
        default) you receive their reaction, never a verdict — the world will
        not confirm you. Touch a veil and they fall silent, which is the only
        answer of that kind you will get."""
        claims = [c for c in claims if c.strip()][:12]
        if not claims:
            return {"error": "The antiquary waits, but you have said nothing."}
        if self.purist:
            return self._reception(claims)
        # benchmark mode
        verdicts = self._graded(claims)
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
