# Notes — souls-lore-gen

## Goal
Dwarf Fortress-style procedural history generator whose *output surface* is
Dark Souls / Elden Ring style item descriptions: the true chronicle is
simulated deterministically, then an LLM renders each item as an incomplete,
biased fragment of that history.

## Log

### 2026-07-05 — initial build
- Checked environment: no `ANTHROPIC_API_KEY` and no `ant` CLI in this
  container (probe call returned 401), so the LLM path can't be exercised
  here. Decision: LLM (Claude Opus 4.8) is the primary lore writer; a
  deterministic template fallback (`--no-llm`) keeps the tool runnable
  offline and is used for the committed sample output.
- Architecture (three layers, DF-style "simulate then narrate"):
  1. `worldsim.py` — seeded, fully deterministic history sim. Picks a
     cosmology archetype (flame / sea / root / moon / song), spawns gods,
     kingdoms, orders, heroes; runs three ages with wars, betrayals,
     ascensions, curses; forges artifacts with provenance chains; and picks
     one *central hidden mystery* that no item may state outright.
  2. `loregen.py` — turns the true chronicle + per-item "knowledge packets"
     into item descriptions. Knowledge packets are the key trick: each item
     only *knows* a subset of true facts, gets a faction bias, and sometimes
     a deliberately false rumor — so the player-facing codex must be
     triangulated across items, like real Souls lore.
  3. `main.py` — CLI. Writes `chronicle.md` (spoilers / ground truth),
     `codex.md` (the deliverable), `world.json` (raw data).
- LLM call design: single streamed `messages.create` on `claude-opus-4-8`
  with adaptive thinking and a `json_schema` structured output
  (`{"items":[{id,name,description}]}`) — one call sees all items at once so
  cross-references and contradictions stay coherent. Style guide in the
  system prompt is written from scratch (pastiche conventions, no copied
  FromSoft text).
- Fallback writer mirrors the same constraints with templates: terse first
  line (function), then 1–2 lore sentences from the knowledge packet, biased
  phrasing per faction kind, hedges ("it is said", "some claim") on the
  false rumor.

### Things that didn't work / gotchas
- First idea was one LLM call *per item* — rejected: loses global coherence
  (items should contradict each other *deliberately*, not accidentally) and
  costs more. One batched call with the full chronicle in context is better.
- Tried probing auth via `ant auth status` — CLI not installed here; the
  SDK probe was the reliable check.
- Determinism gotcha: everything flows through one `random.Random(seed)`;
  no `set` iteration or dict-ordering dependence in generation paths, so the
  same seed reproduces the same world byte-for-byte (needed for comparing
  template vs LLM output on identical worlds).

### Sample output
- `worlds/seed-107/` and `worlds/seed-9021/` generated with `--no-llm`
  (template mode) since this container has no API key. Rerun without
  `--no-llm` and with `ANTHROPIC_API_KEY` set for the real prose.

### 2026-07-06 — depth on demand
- Goal: make depth a *query operation* instead of a bigger upfront sim.
  Design: fractal + lazy expansion, deterministic sub-seeds, append-only
  canon ledger, LLM as constrained elaborator with validated write-back.
- New pieces:
  - `ledger.py` — canon fact store persisted as `ledger.json`; all mutation
    goes through validators (year bounds, participants-can't-act-after-fate,
    unique names, id existence). Chronicle/codex now render from the ledger
    (removed `render_chronicle` from worldsim — single source of truth).
  - `expand.py` — `expand_event(ledger, node)` seeded from
    `hash(seed:node_id)`: per-event-kind templates (great war, betrayal,
    rite, sealing, twilight, generic) produce 2 sub-events + minor figures
    + 0–2 new items whose knowledge packets come from the new sub-events.
  - `loregen.py` rewritten against the ledger; three surfaces
    (describe_items / elaborate / ask_world), each with template fallback.
    `elaborate` merges LLM output only through ledger paths; invalid notes
    are dropped with a warning, and the deterministic skeleton survives any
    LLM failure.
  - Veils: replaced each archetype's flat mystery list with an authored
    3-veil chain (surface secret → the mystery → the deepest reframe).
    Depth-k content may hint only at veil ≤ k.
  - CLI: `generate | deepen | ask | codex`; bare flags still mean generate.
- Verified offline: deepen walks down on repeat (`--item Oathbreaker`
  expanded e23, then e29); expansion of e14 on two divergent world copies
  yields identical children (determinism); the fate-guard rejects
  "Mazirast acting in year 533" (died 523); nested chronicle renders;
  minted items (Torn Standard of Haruienreach) appear in the codex; `ask`
  answers in-world from canon.
- Gotchas hit:
  - Expansion ids depend on expansion *order* (e29 vs e33 for the same
    children) — content is order-independent, ids are not. Documented
    rather than fought; content determinism is what matters for canon.
  - Place names used only inside event text aren't ledger-claimed (only
    full entity names are), so a later expansion could in principle reuse
    one. Collision space is large; accepted.
  - RNG stream shifted vs v1 (removed one `rng.choice` at genesis), so the
    same seeds now produce different worlds than the first commit. Samples
    regenerated.
- LLM paths (`describe_items`/`elaborate`/`ask_world` with a model) are
  untested in this container (401, no key) — they share the merge/validation
  code with the fallback paths, which are tested.

### 2026-07-06 — agent exploration API (MCP)
- Core decision: an exploring agent is a *player*, not a repo reader. The
  epistemic boundary is enforced server-side — fog of war is state
  (`explorations/<name>.json`), never model discipline. Seeker sees only
  item names/descriptions and what it has uncovered; `hidden` fields,
  veils, and false-rumor flags stay on the server.
- `explore.py`: `Exploration` class with the five-tool discovery loop —
  survey (free) → examine (free; returns *leads*: entity/place names found
  in the description) → ask (budgeted; reuses ask_world) → delve (budgeted;
  resolves a lead to the nearest unexpanded event, runs expand+elaborate,
  returns new accounts + minted items; misses are refunded) → theorize
  (claims graded established/consistent/unsupported/contradicted/veiled).
- Two judges: Claude judge (structured output, sees canon + seeker's
  discovered material, notes must not spoil) and an offline lexical judge
  (word-overlap vs canon/veils/discovered text; conservative — cannot
  detect contradictions, documented). Scoring: 3/2/1/0/−1 → makes the whole
  thing a lore-comprehension benchmark with machine-readable ground truth.
- `mcp_server.py`: thin FastMCP stdio wrapper; `--role archivist` adds a
  `canon()` tool for GM/eval harnesses; seekers get an in-world refusal.
- Verified offline on seed-9021: full loop via direct Python (examine
  Oathbreaker → 5 leads → ask → delve Mazirdis → new item "Effects of
  Ishaott" → theorize scored 6 with all four verdict types correct) AND via
  a real MCP stdio handshake (list_tools shows the 6 seeker tools, no canon;
  survey/examine/theorize round-trip; budget persisted across sessions).
- Gotcha: FastMCP tool registration happens per-process with the world dir
  from argv, so one server = one world + one explorer; run several servers
  for several seekers (state files keep them isolated anyway).

### 2026-07-06 — documented exploration (seed-9)
- Played a full seeker run against a fresh sea-archetype world (seed 9) and
  wrote it up as `worlds/seed-9/exploration-journal.md`: 16/16 items, 5
  delves, 4 asks, 10-claim theory scored 24; one veil hit verbatim
  (graded `veiled`), the divine-treason hidden fact missed entirely (the
  dice never leaked it into an item — good difficulty gradient evidence).
- Emergent coherence worth keeping: the secret traitor god rolled as
  Veloryne, *god of storms and unkept promises*, and the sim independently
  hung both broken-promise institutions (Thalenien's church, the cult) off
  his lineage. Nobody wrote that correspondence; the generator's causality
  produced it.
- Delve resolver behavior observed: repeated delves on the same figure
  drill depth-first into freshly created children (Ishirula #2 expanded the
  new battle, not the sealing) because expansion children inherit the
  figure as participant and sort earlier by year. Reasonable, but a
  breadth-first option might serve seekers better.
- Confirmed two lexical-judge over-credits (documented in the journal's
  epilogue): causal speculation and unheld hidden truths can score
  `established` on word overlap. The Claude judge path grades against the
  seeker's actual discovered material.

### 2026-07-06 — discovered-lore compendium
- `Exploration.compendium()` renders "The Book of Found Things": everything
  one explorer has uncovered (examined relics grouped by type, delve
  accounts, archive answers, graded theories, what remains unfound) —
  built purely from exploration state + public surfaces, so it is
  seeker-safe by construction. Exposed as `main.py lore --explorer NAME`
  and as a free `compendium` MCP tool (verified over stdio; tool list now
  7 for seekers).
- Generated for both explorations: seed-9/claude (complete sweep — nothing
  unfound) and seed-9021/seeker (early run — 11 items still unfound), a
  nice contrast between a finished and a barely-started dig.

### 2026-07-06 — purist mode + the space dimension
- Two features to close the gap with the actual ER experience (per the
  "does this emulate ER" analysis): geography, and no verdicts.
- SPACE (ledger.py `ensure_geography`, derived not simulated — idempotent,
  migrates old ledgers on load):
  - place entities (faction seats + a `the Pilgrim Roads` hub + any place
    name appearing in event text, matched by PLACE_SUFFIXES).
  - every event gets a `place`; every artifact a `site` + a `placement`
    line chosen by its last-provenance event kind (sim-controlled evidence
    channel, e.g. fall-of-kingdom → "found at the foot of a throne...").
  - chronicle renders a Places section + per-event "(at X)"; codex prints
    each item's placement in italics.
- explore.py reworked into a spatial loop: survey = your charted MAP (not a
  catalogue); travel (step budget; new ground costs 1, returning free;
  reveals a place's relics + neighbours); look; examine gated to
  current-location-or-found. Adjacency = places named in events at your
  location, + roads always regainable (mostly hub-and-spoke until delving
  forges cross-links). delve now also reveals `new_ground`.
- PURIST MODE (default for seekers): theorize returns a fellow antiquary's
  in-world reception — nod / doubt / SILENCE on a veil — never a verdict or
  score. The true grading is still computed and stored server-side (for
  replay/benchmark) but not exposed. `--benchmark` / `purist=False` restores
  verdicts for eval harnesses; `--role archivist` still gets canon().
- Verified offline: examine-before-travel blocked; placement lines surface
  on look/examine; travel adjacency enforced (can't jump to a far seat);
  purist theorize hides scores and goes silent on a veil claim; benchmark
  mode still returns verdicts+score; MCP now lists 9 tools (survey/look/
  travel/examine/ask/delve/theorize/progress/compendium).
- Documented run: `worlds/seed-5/exploration-journal.md` (song archetype),
  played blind in purist+space mode. Key demonstration: the seeker never
  walked to Mazucaelcrown and so missed the entire central betrayal — under
  the old catalogue API those item names showed up in the opening survey;
  under space, a region unwalked is a plot unknown. The veil was "reached"
  only as the antiquary's refusal to discuss it.
- Minor known blemishes (accepted): kingdom names ending in a place-suffix
  (e.g. Hestnothgate) also become place entities — thematically fine (ER
  blurs realm/place names) but a mild dup; the "seal weakens" placement can
  read "on the roads to the Pilgrim Roads" when its event sits at the hub.

### 2026-07-06 — configurable budget + delving opens new ground (100-step run)
- Request: a 100-step walkthrough. Default step budget was 8, so added an
  optional `budget=` arg to Exploration (records `start_budget` for correct
  spent-so-far reporting in the compendium).
- First 100-step run exposed a real design gap: delving grew *history* huge
  (+160 events, +81 figures) but only +5 places, so the seeker spent 14/100
  steps — geography, not steps, was the limiter. In ER, digging into a lead
  opens a new *area*. Fixed it: every expansion now mints a fresh locale
  ("off the deep roads") and sites its child events + minted relics there;
  `ensure_geography` now fills `placement` independently of `site` so those
  pre-set sites keep. Delve already reports child/​item places as new_ground,
  so digging now grows the *map*.
- Re-run (seed-314, Sundered Moon): 100/100 steps, 80/80 delves, world grew
  28→188 events, 13→55 relics, 16→101 places, 12→93 figures; walked 101/101
  places, examined 54/55 relics. Report: worlds/seed-314/walkthrough-100steps.md
  (world-growth table, abridged run log, purist theory with a veil-1 probe
  that drew the antiquary's silence, full compendium of all discovered lore).
- Determinism note: locale minting draws one namer.place() AFTER the template
  runs, so child-event/relic *content* is unchanged; only a place is appended.
  Committed pre-existing worlds aren't re-expanded, so they're unaffected;
  their ledgers just gain nothing on load (placement already set).

### 2026-07-06 — full review pass
Wrote `selfcheck.py` (structural / causal / epistemic invariants, non-zero
exit = test) and ran it over every committed world. 4,848 checks found 50
failures in three classes; triaged each:

1. FALSE POSITIVE — "veil leak" in seed-5's compendium was line 110 of
   *Theories Ventured*: the seeker's own claim echoed back. The world never
   leaked it (the antiquary answered with silence). Tightened the check:
   veils must not appear in **world-authored** surfaces (descriptions,
   placements, event accounts, codex, ask fragments); a compendium may quote
   one only inside the seeker's own claims. Also dropped the "hidden leak"
   rule for compendia — the template writer copies hidden truths into
   descriptions *hedged*, which is the design, not a leak.

2. REAL BUG — phantom places. `ensure_geography`'s suffix regex swept event
   text for capitalised words ending in a PLACE_SUFFIX, but person-name ENDS
   overlap those suffixes ("-mere"), so figures became walkable places. Worse
   than map noise: it corrupted the placement evidence channel, siting relics
   *inside people* ("kept in a reliquary at Yormere" — a saint; "throne room
   at Ruthmere" — a god). Fixed by excluding names owned by figures; those
   placements now read "at Ostenthasvault" / "at Olearacradle" (the real
   seats). 5 of the 100-step run's 101 places were phantoms (now 96).

3. REAL MODELLING FLAW — `participants` conflated actors with referents, so
   genesis asserted that a god acts 13 years after descending and a sealed
   adversary acts 364 years after entombment. The ledger's fate validator
   would reject both, but genesis builds dataclasses directly and bypasses
   it. Added `Event.referents` (named, not acting): "set out for the place
   where X was lost" and "digging at the seal of X" now list X as a referent.
   Ledger carries/validates them, subgraph includes them, delve resolution
   searches them, selfcheck exempts them from the fate rule.

Also: `start_budget` now backfilled for pre-budget states (compendium
otherwise misreports spend for a resumed custom-budget run); removed an
unused `random` import and a function-local `import re`.

Regenerating worlds wiped the expansions the journals quote, so the
documented runs became unmoored. Fixed properly by making them reproducible:
`demos.py` (transcript / pilgrim / hundred / seeker) regenerates each world
from seed, replays the same actions, and rewrites the report. Verified the
journals' quotes survive the replay. Final state: 6,695 checks, 0 failures;
MCP surface unchanged (9 seeker tools, purist keys only).

### 2026-07-06 — LLM-only: template fallback removed
Decision (user): generation is always LLM-backed. Removed every offline path
rather than leaving it as a hidden second quality tier.

- `loregen.py`: deleted the whole template writer (~88 lines: _FUNCTION_LINES,
  _HEDGES, _CLOSERS, _VEIL_HINTS, _after_hedge, _strip_year, _fallback_*) and
  the template branch of `ask_world`. `model` is now a required-with-default
  arg (`claude-opus-4-8`) on all three surfaces, never `None`.
- Missing-item handling changed from "fill the gaps with templates" to a
  **repair pass**: re-ask for just the omitted items, then raise if any are
  still undescribed. A half-written codex is now an error, not a silent mix.
- `explore.py`: removed `_llm_guard` and `_judge_lexical`; `_graded` is the
  Claude judge only. Purist reception is unchanged — it still derives from a
  real grading, just never an offline one.
- `main.py` / `mcp_server.py` / `demos.py`: `--no-llm` gone.
- Failure is loud and single-line everywhere. The SDK defers its auth check to
  *request* time (constructing `Anthropic()` succeeds without credentials and
  raises `TypeError` later), so `_stream_json` catches both that and
  `AuthenticationError` and re-raises `NoCredentials`; `main.py` turns it into
  `sys.exit(msg)`; `demos.py` surfaces the subprocess's own last stderr line.
  Verified: `main.py generate` → one sentence, exit 1, no traceback.
- `selfcheck.py` split: structural/causal/epistemic + determinism + role
  gating stay **offline** (they only touch ledgers and the pure sim); the
  live purism check (theorize is model-backed) skips with a printed notice
  when credentials are absent. Still 6,694 checks, 0 failures here.

Consequence, stated plainly: this container has no key, so worlds can no
longer be regenerated here and `demos.py` cannot be re-run. The committed
worlds keep their template-era *prose* (labelled as such in the README);
their ledgers are pure simulation and are exactly what a live run reproduces.
Re-running `demos.py all` with credentials rewrites the prose from the same
facts.
