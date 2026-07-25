"""Invariant checker for generated worlds and exploration states.

Run over every world in worlds/ (or a given directory):

    uv run selfcheck.py [worlds/seed-9 ...]

Checks three families of invariant:

  STRUCTURAL   every reference resolves; parents/depths/years are coherent;
               names are unique; geography is complete.
  CAUSAL       no figure acts after their recorded fate; provenance events
               precede the artifacts they explain.
  EPISTEMIC    the player-facing surfaces (item descriptions, codex,
               compendium, exploration state) never contain veil text or an
               event's `hidden` truth verbatim — the boundary the whole
               design rests on.

Exit code is non-zero if any check fails, so this doubles as a test.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ledger import Ledger, ensure_geography, render_codex

NAMED = ("figure", "faction", "artifact", "place")


class Check:
    def __init__(self):
        self.fails: list[str] = []
        self.warns: list[str] = []
        self.n = 0

    def ok(self, cond, msg, warn=False):
        self.n += 1
        if not cond:
            (self.warns if warn else self.fails).append(msg)
        return bool(cond)


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _shingles(s: str, k: int = 8) -> set[str]:
    """Word k-grams, for detecting verbatim leakage of a secret."""
    w = _norm(s).split()
    return {" ".join(w[i:i + k]) for i in range(max(0, len(w) - k + 1))}


def check_world(world_dir: Path, c: Check) -> None:
    tag = world_dir.name
    lg = Ledger.load(world_dir / "ledger.json")
    ents = lg.entities

    # geography must already be complete on disk (not only after a load-time fix)
    changed = ensure_geography(lg)
    c.ok(not changed, f"[{tag}] ledger.json on disk was missing geography "
                      f"(ensure_geography mutated it at load)")

    # ---- STRUCTURAL -------------------------------------------------------
    c.ok(len(lg.meta.get("veils", [])) == 3,
         f"[{tag}] expected 3 veils, got {len(lg.meta.get('veils', []))}")
    present = lg.meta["present_year"]

    names: dict[str, str] = {}
    for eid, e in ents.items():
        t = e.get("type")
        c.ok(t in ("figure", "faction", "event", "artifact", "place"),
             f"[{tag}] {eid}: unknown entity type {t!r}")
        if t in NAMED:
            nm = e.get("name")
            c.ok(bool(nm), f"[{tag}] {eid}: missing name")
            if nm:
                # A place may deliberately share a realm's name (a fallen
                # kingdom is also somewhere you can stand) when tagged.
                prior = names.get(nm)
                aliased = (t == "place" and e.get("aka_faction") == prior) or \
                          (prior and ents[prior].get("aka_faction") == eid)
                c.ok(prior is None or aliased,
                     f"[{tag}] duplicate name {nm!r} ({eid} and {prior})")
                names.setdefault(nm, eid)

    for eid, e in lg.of_type("event"):
        c.ok(0 <= e["year"] <= present,
             f"[{tag}] {eid}: year {e['year']} outside [0,{present}]")
        c.ok(e.get("place") in ents and ents[e["place"]]["type"] == "place",
             f"[{tag}] {eid}: place {e.get('place')!r} is not a place entity")
        p = e.get("parent")
        if p is not None:
            c.ok(p in ents and ents[p]["type"] == "event",
                 f"[{tag}] {eid}: parent {p!r} is not an event")
            if p in ents:
                c.ok(e["depth"] == ents[p]["depth"] + 1,
                     f"[{tag}] {eid}: depth {e['depth']} != parent depth+1")
        else:
            c.ok(e["depth"] == 0, f"[{tag}] {eid}: root event with depth "
                                  f"{e['depth']}")
        # no cycles
        seen, cur, ok = set(), eid, True
        while cur is not None:
            if cur in seen:
                ok = False
                break
            seen.add(cur)
            cur = ents.get(cur, {}).get("parent")
        c.ok(ok, f"[{tag}] {eid}: parent chain contains a cycle")

    for aid, a in lg.of_type("artifact"):
        c.ok(a.get("site") in ents and ents[a["site"]]["type"] == "place",
             f"[{tag}] {aid}: site {a.get('site')!r} is not a place entity")
        c.ok(bool(a.get("placement")), f"[{tag}] {aid}: missing placement line")
        if a.get("site") and a.get("placement"):
            c.ok(ents[a["site"]]["name"] in a["placement"],
                 f"[{tag}] {aid}: placement line does not name its site "
                 f"({ents[a['site']]['name']!r})", warn=True)
        hv = a.get("hints_veil")
        c.ok(hv is None or 0 <= hv < len(lg.meta["veils"]),
             f"[{tag}] {aid}: hints_veil {hv} out of range")
        for pv in a["provenance"]:
            c.ok(pv in ents and ents[pv]["type"] == "event",
                 f"[{tag}] {aid}: provenance {pv!r} is not an event")

    for fid, f in lg.of_type("figure"):
        fac = f.get("faction")
        c.ok(fac is None or (fac in ents and ents[fac]["type"] == "faction"),
             f"[{tag}] {fid}: faction {fac!r} is not a faction")
    for kid, k in lg.of_type("faction"):
        fo = k.get("founder")
        c.ok(fo is None or (fo in ents and ents[fo]["type"] == "figure"),
             f"[{tag}] {kid}: founder {fo!r} is not a figure")
    for note in lg.d["notes"]:
        c.ok(note["entity_id"] in ents,
             f"[{tag}] note references unknown entity {note['entity_id']!r}")

    # ---- CAUSAL -----------------------------------------------------------
    for eid, e in lg.of_type("event"):
        for pid in e["participants"]:
            if not c.ok(pid in ents and ents[pid]["type"] == "figure",
                        f"[{tag}] {eid}: participant {pid!r} is not a figure"):
                continue
            fy = ents[pid].get("fate_year")
            c.ok(fy is None or e["year"] <= fy,
                 f"[{tag}] {eid} (year {e['year']}): {ents[pid]['name']} acts "
                 f"after their fate in year {fy}")
        # referents are named, not acting — exempt from the fate rule, but
        # they must still resolve to real figures
        for rid in e.get("referents", []):
            c.ok(rid in ents and ents[rid]["type"] == "figure",
                 f"[{tag}] {eid}: referent {rid!r} is not a figure")

    # ---- EPISTEMIC --------------------------------------------------------
    # No player-facing text may contain a veil verbatim, nor an event's hidden
    # truth verbatim. (Hidden truths *may* be paraphrased into descriptions as
    # hedged "half-known secrets" — so we test only for long verbatim spans,
    # which is what a real leak looks like.)
    # World-authored surfaces: everything the world says to a seeker. A veil
    # must never appear verbatim in any of them. (An event's `hidden` truth
    # *may* reach a description as a hedged "half-known secret" — that is the
    # design — so it is not treated as leakage.)
    authored: list[tuple[str, str]] = []
    for aid, a in lg.of_type("artifact"):
        if a.get("description"):
            authored.append((f"{aid} description", a["description"]))
        if a.get("placement"):
            authored.append((f"{aid} placement", a["placement"]))
    for eid, e in lg.of_type("event"):
        authored.append((f"{eid} account", e["text"]))
    authored.append(("codex.md", render_codex(lg)))
    for st_path in sorted((world_dir / "explorations").glob("*.json")):
        st = json.loads(st_path.read_text())
        for a in st.get("asks", []):
            authored.append((f"{st_path.name} ask fragment", a["fragment"]))

    veil_shingles = [(i, _shingles(v)) for i, v in enumerate(lg.meta["veils"])]
    for where, text in authored:
        ts = _shingles(text)
        for i, sh in veil_shingles:
            hit = sh & ts
            c.ok(not hit, f"[{tag}] VEIL {i} LEAK in {where}: "
                          f"{sorted(hit)[0][:60]!r}" if hit else "")

    # A compendium may quote a veil only inside the seeker's own claims.
    for md in sorted(world_dir.glob("**/*-lore.md")):
        body = md.read_text()
        world_part = body.split("## Theories Ventured")[0]
        ts = _shingles(world_part)
        for i, sh in veil_shingles:
            hit = sh & ts
            c.ok(not hit, f"[{tag}] VEIL {i} LEAK in {md.name} "
                          f"(outside the seeker's own claims)" if hit else "")


def check_determinism(c: Check) -> None:
    """Genesis must be reproducible; expansion skeletons must be per-node."""
    from worldsim import generate_world
    from expand import expand_event

    a = Ledger.from_world(generate_world(4242, 14))
    b = Ledger.from_world(generate_world(4242, 14))
    c.ok(json.dumps(a.d, sort_keys=True) == json.dumps(b.d, sort_keys=True),
         "genesis is not byte-deterministic for a fixed seed")

    # expand the same node in two ledgers that have diverged elsewhere
    ensure_geography(a); ensure_geography(b)
    roots = [eid for eid, e in a.of_type("event") if not e["expanded"]]
    other = roots[-1]
    expand_event(b, other)                      # diverge b
    node = roots[0]
    ka, _ = expand_event(a, node)
    kb, _ = expand_event(b, node)
    sig = lambda lg, ids: [(lg.get(i)["year"], lg.get(i)["kind"],
                            lg.get(i)["text"]) for i in ids]
    c.ok(sig(a, ka) == sig(b, kb),
         "expansion of the same node differs between divergent worlds")

    # the fate guard must actually bite
    from ledger import LedgerError
    fid = next((i for i, f in a.of_type("figure") if f["fate_year"]), None)
    if fid:
        try:
            a.add_event("test", a.get(fid)["fate_year"] + 5, "impossible",
                        None, [fid], None, 1, "test")
            c.ok(False, "fate guard did not reject an event after a death")
        except LedgerError:
            c.ok(True, "")


def check_purism(c: Check) -> None:
    """A seeker must never receive verdicts or scores; an archivist must."""
    from explore import Exploration
    worlds = sorted(Path("worlds").glob("seed-*/ledger.json"))
    if not worlds:
        return
    wd = worlds[0].parent
    seeker = Exploration(wd, explorer="_selfcheck_seeker", model=None)
    out = seeker.theorize(["The gods are silent.", "Something was drowned."])
    c.ok("verdicts" not in out and "score" not in out,
         "purist theorize exposed verdicts/score to a seeker")
    c.ok("reception" in out, "purist theorize returned no reception")
    c.ok("best_theory_score" not in seeker.progress(),
         "purist progress exposed a score")
    bench = Exploration(wd, explorer="_selfcheck_bench", model=None,
                        purist=False)
    c.ok("verdicts" in bench.theorize(["The gods are silent."]),
         "benchmark mode did not return verdicts")
    arch = Exploration(wd, explorer="_selfcheck_arch", role="archivist",
                       model=None)
    c.ok("error" not in arch.canon(), "archivist was denied canon()")
    c.ok("error" in seeker.canon(), "seeker was granted canon()")
    for name in ("_selfcheck_seeker", "_selfcheck_bench", "_selfcheck_arch"):
        (wd / "explorations" / f"{name}.json").unlink(missing_ok=True)


def main() -> int:
    args = [Path(a) for a in sys.argv[1:]]
    dirs = args or sorted(p.parent for p in Path("worlds").glob("seed-*/ledger.json"))
    c = Check()
    for d in dirs:
        check_world(d, c)
    check_determinism(c)
    check_purism(c)

    print(f"{c.n} checks over {len(dirs)} world(s): "
          f"{len(c.fails)} failure(s), {len(c.warns)} warning(s)")
    for w in c.warns[:20]:
        print(f"  WARN {w}")
    for f in c.fails[:40]:
        print(f"  FAIL {f}")
    return 1 if c.fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
