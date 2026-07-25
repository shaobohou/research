"""Reproducible demo runs — the documented walkthroughs, as code.

    uv run demos.py transcript   # seed-7  → worlds/seed-7/full-walkthrough.md
    uv run demos.py pilgrim      # seed-5  → replays the journal's moves
    uv run demos.py hundred      # seed-314 → walkthrough-100steps.md
    uv run demos.py all

Each demo generates its world from the seed if absent, replays a fixed
sequence of seeker actions, and writes its report. Because genesis and
expansion are deterministic, re-running after a code change reproduces the
same world and refreshes the reports — which is how the committed documents
stay honest.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from explore import Exploration


def _generate(seed: int) -> None:
    """Regenerate a world, surfacing the CLI's own message on failure —
    most often "credentials are required", which is not a stack-trace event."""
    r = subprocess.run([sys.executable, "main.py", "generate",
                        "--seed", str(seed)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit((r.stderr or r.stdout).strip().splitlines()[-1])


def _fresh(seed: int, explorer: str, **kw) -> Exploration:
    """A world reset to genesis with a clean explorer — demos must not
    accumulate state across runs."""
    d = Path(f"worlds/seed-{seed}")
    _generate(seed)
    (d / "explorations").mkdir(exist_ok=True)
    (d / "explorations" / f"{explorer}.json").unlink(missing_ok=True)
    return Exploration(d, explorer=explorer, **kw)


def _first_sentence(desc: str) -> str:
    body = desc.split("\n\n")[-1]
    return body.split(". ")[0].strip().rstrip(".") + "."


# ---------------------------------------------------------------------------
# 1. seed-7 — the full literal transcript
# ---------------------------------------------------------------------------

def demo_transcript() -> Path:
    e = _fresh(7, "warden")
    lg = e.lg
    log: list[tuple[str, object, str | None]] = []

    def rec(call, result, note=None):
        log.append((call, result, note))

    rec("survey()", e.survey())
    rec('examine("Hollow Crown")', e.examine("Hollow Crown"),
        "we have walked nowhere; knowledge is gated by the body")

    known_figures: Counter[str] = Counter()
    walked: set[str] = set()
    frontier = [p["place"] for p in e.survey()["places_known"]
                if p["status"] == "heard of"]
    while frontier and e.state["budget"]["steps"] > 0:
        place = frontier.pop(0)
        if place in walked:
            continue
        r = e.travel(place)
        if "error" in r:
            rec(f'travel("{place}")', r)
            continue
        walked.add(place)
        rec(f'travel("{place}")', r)
        for nb in r.get("ways_onward", []):
            if nb not in walked and nb != "the Pilgrim Roads":
                frontier.append(nb)
        for relic in r["relics_here"]:
            ex = e.examine(relic["name"])
            rec(f'examine("{relic["name"]}")', ex)
            for lead in ex.get("leads", []):
                if lead["kind"] == "figure":
                    known_figures[lead["name"]] += 1

    recurring = [n for n, _ in known_figures.most_common(2)]
    for name in recurring:
        rec(f'ask("Who was {name}?")',
            e.ask(f"Who was {name}, and what became of them?"))
    for name in recurring:
        r = e.delve(name)
        rec(f'delve("{name}")', r)
        for place in (r.get("new_ground") or []):
            tr = e.travel(place)
            rec(f'travel("{place}")', tr, "new ground opened by the dig")
            for relic in tr.get("relics_here", []):
                rec(f'examine("{relic["name"]}")', e.examine(relic["name"]))

    claims, seen = [], set()
    for aid in e.state["discovered"]:
        a = lg.get(aid)
        if a.get("description"):
            s = _first_sentence(a["description"])
            if s.lower()[:40] not in seen:
                seen.add(s.lower()[:40])
                claims.append(s)
        if len(claims) == 3:
            break
    veil0 = lg.meta["veils"][0]
    claims.append(veil0[0].upper() + veil0[1:])        # veil-1 probe
    claims.append("The last knight became the god he went to find.")   # overreach
    rec("theorize([... 5 claims ...])", e.theorize(claims),
        "purist mode — a fellow antiquary's reaction, never a verdict")
    rec("progress()", e.progress())
    comp = e.compendium()
    rec("compendium()", comp)

    lines = [
        "# Full Walkthrough — seed-7, the world of the Pale Root", "",
        "*A complete, unedited transcript of one seeker (\"warden\") playing the "
        "exploration API in the default **spatial + purist** mode. Every tool "
        "call and its literal output, in order. Reproduce with "
        "`uv run demos.py transcript`.*", "",
        "> Loop: `survey` (map) → `travel` → `look`/`examine` → `ask` → `delve` "
        "→ `theorize`. You learn a place's relics only by walking there; no one "
        "will ever tell you that you are right.", ""]
    for call, result, note in log:
        lines.append(f"## ▶ `{call}`")
        if note:
            lines.append(f"*{note}*")
        lines.append("")
        if isinstance(result, str):
            lines.append(result)
        else:
            lines.append("```json\n" + json.dumps(result, indent=2) + "\n```")
        lines.append("")
    lines += [
        "---", "",
        "## Epilogue — the truth (SPOILERS)", "",
        "Checked against `chronicle.md` and the veils:", "",
        "- **The mortal age, largely recovered.** The seeker found the fallen "
        "god (his soul *\"taken from a throne room where nothing else was "
        "disturbed\"* — a departure, not a death), the rite that fed a saint to "
        "the Root while its own priest *\"suspected as much,\"* and — by "
        "following the one cross-link into the fallen kingdom — the betrayal "
        "itself.",
        "- **The veil, answered only by silence.** The fourth claim is **veil 1 "
        "of 3** verbatim. In purist mode the antiquary did not confirm it; they "
        "went quiet and told the seeker to speak no further. That refusal is the "
        "only signal of hidden truth a seeker gets, and it is deniable. Veils 2 "
        "and 3 were never approached — correct for a first pilgrimage.",
        "- **The overreach, correctly doubted** — *\"the last knight became the "
        "god he went to find\"* drew *\"you reach past your evidence\"*, a "
        "doubt rather than a verdict.", ""]
    out = e.world_dir / "full-walkthrough.md"
    out.write_text("\n".join(lines))
    return out


# ---------------------------------------------------------------------------
# 2. seed-5 — replay the pilgrim's journal moves
# ---------------------------------------------------------------------------

def demo_pilgrim() -> Path:
    e = _fresh(5, "pilgrim")
    for dest in ["Loachgate", "Wrenwynreach", "Athagarcradle",
                 "Karesswyncrown", "Mazoscrown"]:
        e.travel(dest)
    for item in ["Soul of Sylenmoth", "Echo of Saint Sereth",
                 "Ulorast's Set", "Hymn of Sylenmoth"]:
        e.examine(item)
    e.ask("Who was Nimaeast, who urged the rite of restoration?")
    e.ask("Did Ulorast fall to the marked, or lead them?")
    e.delve("Ulorast")
    e.delve("Sylenmoth")
    e.theorize([
        "Sylenmoth descended below the world to look on the Founding Chord "
        "and did not return.",
        "The rite of restoration did not restore the Chord; it only slowed the "
        "waning, and Nimaeast suspected as much.",
        "Ulorast, last-sworn of the Order of the Chord, went after Sylenmoth "
        "and neither fell to the marked nor led them cleanly — the order "
        "believes no telling.",
        "The bells are rung not to honour the Chord but to drown out something "
        "singing beneath it.",
        "The waning is no accident.",
    ])
    out = e.world_dir / "explorations" / "pilgrim-lore.md"
    out.write_text(e.compendium())
    return out


# ---------------------------------------------------------------------------
# 3. seed-314 — the 100-step run
# ---------------------------------------------------------------------------

BIG_BUDGET = {"steps": 100, "delves": 80, "asks": 50}


def demo_hundred() -> Path:
    e = _fresh(314, "cartographer", budget=BIG_BUDGET)
    lg = e.lg
    count = lambda t: len(lg.of_type(t))
    kinds = ("event", "artifact", "place", "figure")
    start = {t: count(t) for t in kinds}
    log: list[str] = [f"# start: {start['event']} events, {start['artifact']} "
                      f"items, {start['place']} places, {start['figure']} figures"]

    def drain_travel():
        while e.state["budget"]["steps"] > 0:
            todo = [p for p in e.state["known_places"]
                    if p not in set(e.state["visited"])]
            if not todo:
                return
            r = e.travel(e._pname(todo[0]))
            if "error" in r:
                e.state["visited"].append(todo[0])
                continue
            got = 0
            for relic in r.get("relics_here", []):
                e.examine(relic["name"])
                got += 1
            if got:
                log.append(f"  travelled {r['arrived']} (steps "
                           f"{r['steps_left']}) — examined {got} relic(s)")

    while True:
        drain_travel()
        if e.state["budget"]["steps"] <= 0:
            log.append("== step budget exhausted ==")
            break
        if e.state["budget"]["delves"] <= 0:
            log.append("== delve budget exhausted ==")
            break
        unexp = sorted((eid for eid, ev in lg.of_type("event")
                        if not ev["expanded"]),
                       key=lambda i: (lg.get(i)["depth"], int(i[1:])))
        if not unexp:
            log.append("== nothing left to delve; world fully expanded ==")
            break
        target = unexp[0]
        d = e.delve(target)
        if "error" in d:
            log.append(f"  delve {target}: {d['error'][:50]}")
            continue
        log.append(f"  delve {target}: +{len(d.get('findings', []))} accounts, "
                   f"+{len(d.get('new_items', []))} items, new ground: "
                   f"{d.get('new_ground') or '—'}")

    figs: Counter[str] = Counter()
    for aid in e.state["discovered"]:
        for lead in e._leads(lg.get(aid).get("description") or "", {aid}):
            if lead["kind"] == "figure":
                figs[lead["name"]] += 1
    for name, _ in figs.most_common(6):
        e.ask(f"Who was {name}, and what became of them?")
    log.append(f"  asked about {min(6, len(figs))} recurring figures")

    claims, seen = [], set()
    for aid in e.state["discovered"]:
        a = lg.get(aid)
        if a.get("description"):
            s = _first_sentence(a["description"])
            if s.lower()[:40] not in seen:
                seen.add(s.lower()[:40])
                claims.append(s)
        if len(claims) == 4:
            break
    veil0 = lg.meta["veils"][0]
    claims.append(veil0[0].upper() + veil0[1:])
    recept = e.theorize(claims)

    end = {t: count(t) for t in kinds}
    prog = e.progress()
    lines = [
        f"# 100-Step Walkthrough — seed-314, the world of {lg.meta['primordial']}",
        "",
        "*A large-budget run (100 steps, 80 delves, 50 asks) by the seeker "
        "\"cartographer\", in spatial + purist mode. The point "
        "of a big step budget is to force the world to **grow**: the steps are "
        "spent walking to ground that does not exist until you dig for it. Each "
        "dig opens a fresh locale off the deep roads, so an exhaustive run is a "
        "loop of *dig to open ground, walk to it, dig again*. Reproduce with "
        "`uv run demos.py hundred`.*", "",
        "## World growth (the headline)", "",
        "| | events | relics | places | figures |",
        "|---|---:|---:|---:|---:|",
        f"| at genesis | {start['event']} | {start['artifact']} | "
        f"{start['place']} | {start['figure']} |",
        f"| after the run | {end['event']} | {end['artifact']} | "
        f"{end['place']} | {end['figure']} |",
        f"| **grew by** | **+{end['event'] - start['event']}** | "
        f"**+{end['artifact'] - start['artifact']}** | "
        f"**+{end['place'] - start['place']}** | "
        f"**+{end['figure'] - start['figure']}** |", "",
        f"Budget spent: **{BIG_BUDGET['steps'] - prog['steps_left']}/100 "
        f"steps**, {BIG_BUDGET['delves'] - prog['delves_left']}/80 delves, "
        f"{BIG_BUDGET['asks'] - prog['asks_left']}/50 asks. Walked "
        f"{prog['places_walked']} places; examined {prog['relics_examined']} "
        f"relics.", "",
        "## Run log (abridged — one line per productive action)", "",
        "```", *log, "```", "",
        "## The theory, and its reception (purist)", ""]
    for r in recept["reception"]:
        lines += [f"- **{r['claim']}**", f"  - {r['reception']}", ""]
    lines += [f"*Closing:* {recept['closing']}", "", "---", "",
              "## The Book of Found Things (everything discovered)", "",
              e.compendium(), ""]
    out = e.world_dir / "walkthrough-100steps.md"
    out.write_text("\n".join(lines))
    return out


# ---------------------------------------------------------------------------
# 4. seed-9 — restore the accounts quoted by the (catalogue-era) journal
# ---------------------------------------------------------------------------

def demo_seeker() -> Path:
    """The seed-9 journal predates spatial gating, so its *examines* cannot be
    replayed literally. Its delves can: this restores the unearthed accounts
    the journal quotes, so a reader who goes looking still finds them."""
    e = _fresh(9, "claude")
    for target in ["Tide of Saint Yormere", "Ishirula", "Ishirula",
                   "Mazamund", "War-Brine"]:
        e.delve(target)
    for q in ["Who was Thalenien, who urged the rite of restoration?",
              "What did Mazamund find in the place where Sylorien was lost?",
              "Who was Veremis, who walked at the saint's left hand?",
              "What became of the wardens who keep the seal of Ishirula?"]:
        e.ask(q)
    out = e.world_dir / "explorations" / "claude-lore.md"
    out.write_text(e.compendium())
    return out


DEMOS = {"transcript": demo_transcript, "pilgrim": demo_pilgrim,
         "hundred": demo_hundred, "seeker": demo_seeker}


def main() -> int:
    which = sys.argv[1:] or ["all"]
    names = list(DEMOS) if which == ["all"] else which
    for name in names:
        fn = DEMOS.get(name)
        if fn is None:
            print(f"unknown demo {name!r}; choose from {', '.join(DEMOS)} or all")
            return 2
        print(f"wrote {fn()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
