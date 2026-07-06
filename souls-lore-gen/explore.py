"""Agent-facing exploration API: the world as a discovery game.

An exploring agent is a *player*, not a reader of the repo. This module
enforces the epistemic boundary: the seeker sees only the diegetic surface
(item names, descriptions, in-world fragments) plus whatever it has
uncovered, while the ledger's hidden layer (event `hidden` fields, veils,
false-rumor flags) stays server-side. Fog of war is state, not model
discipline: per-explorer progress persists in
worlds/seed-N/explorations/<name>.json.

Five tools form the discovery loop:

    survey     the shop window: item names/types, factions heard of
    examine    an item's description + leads (names it mentions)
    ask        an in-world fragment answering a question (costs budget)
    delve      follow a lead: expands the world behind it (costs budget)
    theorize   claims graded against hidden canon, without revealing it

Errors are diegetic ("no record survives...") so nothing leaks through
error strings. All methods return JSON-serializable dicts, so the MCP
wrapper (mcp_server.py) is a one-liner per tool.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from ledger import Ledger, LedgerError, render_chronicle, render_codex
from expand import expand_event
from loregen import ask_world, elaborate

DEFAULT_BUDGET = {"delves": 5, "asks": 8}

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
                 role: str = "seeker", model: str | None = None):
        self.world_dir = Path(world_dir)
        ledger_path = self.world_dir / "ledger.json"
        if not ledger_path.exists():
            raise FileNotFoundError(f"no world at {ledger_path}")
        self.lg = Ledger.load(ledger_path)
        self.explorer = explorer
        self.role = role
        self.model = model
        self.state_path = self.world_dir / "explorations" / f"{explorer}.json"
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text())
        else:
            self.state = {
                "explorer": explorer,
                "discovered": [],          # artifact ids examined
                "asks": [],                # {question, fragment}
                "delves": [],              # {target, node, found}
                "theories": [],            # {claims, verdicts}
                "budget": dict(DEFAULT_BUDGET),
            }

    # -- plumbing ---------------------------------------------------------------

    def _save_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2))

    def _save_world(self):
        self.lg.save(self.world_dir / "ledger.json")
        (self.world_dir / "chronicle.md").write_text(render_chronicle(self.lg))
        (self.world_dir / "codex.md").write_text(render_codex(self.lg))

    def _spend(self, kind: str) -> bool:
        if self.state["budget"][kind] <= 0:
            return False
        self.state["budget"][kind] -= 1
        return True

    def _leads(self, text: str, exclude: set[str]) -> list[dict]:
        leads, seen = [], set()
        for eid, e in self.lg.entities.items():
            if eid in exclude or e["type"] == "event":
                continue
            nm = e.get("name")
            if nm and nm in text and nm not in seen:
                seen.add(nm)
                kind = "item" if e["type"] == "artifact" else e["type"]
                leads.append({"name": nm, "kind": kind})
        for _, k in self.of_factions():
            if k["seat"] in text and k["seat"] not in seen:
                seen.add(k["seat"])
                leads.append({"name": k["seat"], "kind": "place"})
        return leads

    def of_factions(self):
        return self.lg.of_type("faction")

    # -- tools --------------------------------------------------------------------

    def survey(self) -> dict:
        """The shop window: what exists, no lore."""
        items = [{"id": aid, "name": a["name"], "type": a["item_type"],
                  "examined": aid in self.state["discovered"]}
                 for aid, a in sorted(self.lg.of_type("artifact"))]
        factions = [{"name": k["name"], "kind": k["kind"], "seat": k["seat"]}
                    for _, k in self.of_factions()]
        return {
            "world": f"seed-{self.lg.meta['seed']} ({self.lg.meta['archetype_key']})",
            "epigraph": self.lg.meta["epigraph"],
            "ages": [a["name"] for a in self.lg.d["ages"]],
            "items": items,
            "factions_heard_of": factions,
            "budget": dict(self.state["budget"]),
        }

    def examine(self, item: str) -> dict:
        """Read an item's description; marks it discovered, returns leads."""
        try:
            aid, a = self.lg.find_artifact(item)
        except LedgerError:
            return {"error": f"No record survives of a thing called "
                             f"\"{item}\". Perhaps it goes by another name."}
        if aid not in self.state["discovered"]:
            self.state["discovered"].append(aid)
            self._save_state()
        desc = a["description"] or "(the entry is water-stained and unreadable)"
        return {
            "id": aid, "name": a["name"], "type": a["item_type"],
            "description": desc,
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
        # direct event id
        if re.fullmatch(r"e\d+", t) and t in self.lg.entities:
            return self._first_unexpanded([t])
        # item -> its provenance
        try:
            _, a = self.lg.find_artifact(t)
            return self._first_unexpanded(list(reversed(a["provenance"])))
        except LedgerError:
            pass
        tl = t.lower()
        # figure -> events they took part in
        for fid, f in self.lg.of_type("figure"):
            if f["name"].lower() in tl or tl in f["name"].lower():
                roots = [eid for eid, e in self.lg.of_type("event")
                         if fid in e["participants"]]
                roots.sort(key=lambda eid: self.lg.get(eid)["year"])
                return self._first_unexpanded(roots)
        # faction or place -> events whose text mentions the name
        names = [(k["name"], k["name"]) for _, k in self.of_factions()]
        names += [(k["seat"], k["seat"]) for _, k in self.of_factions()]
        for nm, _ in names:
            if nm.lower() in tl or tl == nm.lower():
                roots = [eid for eid, e in self.lg.of_type("event")
                         if nm in e["text"]]
                roots.sort(key=lambda eid: self.lg.get(eid)["year"])
                return self._first_unexpanded(roots)
        return None

    def delve(self, target: str) -> dict:
        """Follow a lead: materialize a level of depth behind it."""
        if not self._spend("delves"):
            self._save_state()
            return {"error": "The lanterns are spent; no more delving today. "
                             "(delve budget spent)"}
        node = self._resolve_delve(target)
        if node is None:
            self.state["budget"]["delves"] += 1     # refund a miss
            self._save_state()
            return {"error": f"The trail of \"{target}\" leads nowhere the "
                             f"records reach — or it has been dug bare "
                             f"already. Try another name, or a place."}
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

        findings = []
        for cid in child_ids:
            c = self.lg.get(cid)
            findings.append({"id": f"frag:{cid}", "year": c["year"],
                             "account": c["text"]})   # hidden stays hidden
        new_items = [{"id": aid, "name": self.lg.get(aid)["name"],
                      "type": self.lg.get(aid)["item_type"]}
                     for aid in item_ids]
        self.state["delves"].append(
            {"target": target, "node": node,
             "found": [f["id"] for f in findings] + [i["id"] for i in new_items]})
        self._save_state()
        return {"findings": findings, "new_items": new_items,
                "delves_left": self.state["budget"]["delves"],
                "note": "New items can be examined; new names can be asked "
                        "after or delved into."}

    # -- theorize -----------------------------------------------------------------

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
        found_frags = [d for d in self.state["asks"]] + self.state["delves"]
        user = (
            "You are the hidden judge of a lore-discovery game. Grade each "
            "claim against the TRUE chronicle:\n"
            "- established: true, AND the seeker's discovered material "
            "supports it\n"
            "- consistent: true in canon, but the seeker has no evidence yet\n"
            "- unsupported: canon is silent either way\n"
            "- contradicted: false per canon\n"
            "- veiled: the claim touches a veil (whether right or wrong)\n"
            "The note must be one in-world sentence that NEVER reveals canon "
            "the seeker hasn't found, and never states a veil. For veiled "
            "claims the note should be some variant of the archives going "
            "quiet.\n\n"
            "=== TRUE CHRONICLE ===\n" + render_chronicle(self.lg) + "\n"
            "=== VEILS ===\n" + _veil_block(self.lg) + "\n"
            "=== SEEKER'S DISCOVERED MATERIAL ===\n" +
            json.dumps({"examined_items": [{"name": d["name"],
                                            "description": d["description"]}
                                           for d in discovered],
                        "fragments": found_frags}, indent=2) + "\n\n"
            "=== CLAIMS ===\n" + json.dumps(claims, indent=2)
        )
        data = _stream_json(self.model, "You grade precisely and reveal nothing.",
                            user, self._JUDGE_SCHEMA)
        return [v for v in data["verdicts"] if v["verdict"] in VERDICTS]

    def _judge_lexical(self, claims: list[str]) -> list[dict]:
        """Offline judge: overlap-based, conservative. Cannot detect
        contradictions; 'established' requires overlap with discovered text."""
        def words(s: str) -> set[str]:
            return {w.strip(".,;:—\"'()").lower() for w in s.split()
                    if len(w) > 3}

        canon_texts = []
        for eid, e in self.lg.of_type("event"):
            canon_texts.append(e["text"])
            if e["hidden"]:
                canon_texts.append(e["hidden"])
        canon_texts += [n["text"] for n in self.lg.d["notes"]]
        discovered_text = " ".join(
            (self.lg.get(aid)["description"] or "")
            for aid in self.state["discovered"])
        discovered_words = words(discovered_text)

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

    def theorize(self, claims: list[str]) -> dict:
        """Submit claims about the true history; graded without spoilers."""
        claims = [c for c in claims if c.strip()][:12]
        if not claims:
            return {"error": "The judge waits, but nothing was claimed."}
        if self.model is None:
            verdicts = self._judge_lexical(claims)
        else:
            verdicts = _llm_guard(self._judge_llm, claims,
                                  fallback=lambda: self._judge_lexical(claims))
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
        return {
            "explorer": self.explorer,
            "items_examined": f"{len(self.state['discovered'])}/{n_items}",
            "asks_left": self.state["budget"]["asks"],
            "delves_left": self.state["budget"]["delves"],
            "theories_submitted": len(self.state["theories"]),
            "best_theory_score": max(
                (t["score"] for t in self.state["theories"]), default=None),
        }

    def canon(self) -> dict:
        """Full ledger + veils. Archivist lens only."""
        if self.role != "archivist":
            return {"error": "The inner archive is barred to seekers."}
        return self.lg.d
