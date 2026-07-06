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
