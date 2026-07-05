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
