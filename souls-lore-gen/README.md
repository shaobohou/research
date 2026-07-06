# souls-lore-gen

A Dwarf Fortress-style procedural history generator whose player-facing output
is **Dark Souls / Elden Ring style item descriptions** — the true history is
simulated, then deliberately shattered into incomplete, biased fragments that
must be triangulated across items. The world is **deep on demand**: any event
can be expanded into finer sub-events (with new minor figures and new items)
lazily, reproducibly, and without ever contradicting established canon.

## How it works

```
seed ──▶ worldsim.py ──▶ genesis: gods, ages, wars, betrayals, artifacts
              │                   with provenance, 3 nested mystery VEILS
              ▼
         ledger.py      the canon ledger (worlds/seed-N/ledger.json):
              │         append-only fact store; every later assertion is
              │         validated against it (years, deaths, name collisions)
              ▼
   ┌─ deepen ─────────────────────────────────────────────────┐
   │  expand.py   deterministic skeleton: hash(seed, node_id)  │
   │      │       → sub-events, minor figures, 0–2 new items   │
   │      ▼                                                    │
   │  loregen.elaborate   LLM enriches prose + adds texture    │
   │                      notes, merged through validated      │
   │                      ledger paths (write-back = canon)    │
   └───────────────────────────────────────────────────────────┘
              ▼
         codex.md  (item lore, no spoilers)   chronicle.md  (nested ground truth)
```

Why it feels like Souls lore:

- **Simulate first, narrate second** (the DF move): every description is
  backed by real events with causality, so fragments cross-reference — the
  same betrayal shows up in a crown, a blade, and a hanged traitor's fate.
- **Knowledge packets**: an item only "knows" its provenance chain, plus a
  hedged glimpse (50%) of any hidden layer. ~35% of items embed one
  confidently wrong rumor, unmarked. Faction bias colors everything (and,
  Souls-classically, the heretics are *nearer* the truth than the church).
- **Layered veils instead of one secret**: each world has a 3-veil mystery
  chain — each veil partially true, reframed by the next. Depth-k content may
  hint only at veil k, so deepening doesn't just add trivia; it *reinterprets*
  what shallower items already said.
- **Depth on demand**: expansion is seeded from `(world_seed, node_id)`, so
  expanding a node always yields the same skeleton no matter when you do it.
  New facts — including the LLM's inventions — are persisted to the ledger,
  so the world *remembers*: ask about the same envoy twice and the answers
  agree.

## Usage

```sh
# Full experience — needs ANTHROPIC_API_KEY (or an `ant auth login` profile).
# Add --no-llm to any command for deterministic template prose, no key needed.
uv run main.py generate --seed 107 --items 14

# Depth on demand: expand the event behind an item (or --node e14).
# Repeating walks down: parent -> first unexpanded child -> ...
uv run main.py deepen --seed 107 --item "Oathbreaker"

# Ask the world a question; answered in-world, from canon only.
uv run main.py ask --seed 107 "Who was Irveth the Saltborn?"

uv run main.py codex --seed 107      # re-render chronicle.md / codex.md
```

Outputs land in `worlds/seed-<N>/`: `ledger.json` (canon), `codex.md`,
`chronicle.md` (nested timeline, veils under a spoiler warning), `answers.md`.

## Exploring as an LLM agent (MCP)

The world is also playable by *another agent* as a discovery game, over MCP:

```sh
claude mcp add lore -- uv run --project . mcp_server.py --world worlds/seed-9021
```

The exploring agent is a **player, not a reader of the repo** — the server
enforces the epistemic boundary. Six tools form the discovery loop:

| tool | cost | what it does |
|---|---|---|
| `survey()` | free | the shop window: item names/types, factions heard of, budget |
| `examine(item)` | free | an item's description + **leads** (names it mentions) |
| `ask(question)` | 1 ask | an in-world fragment, from canon, never the veils |
| `delve(target)` | 1 delve | follow a lead (item/figure/place/event id): expands the world behind it, returning new accounts and sometimes **new items** |
| `theorize(claims)` | free | each claim graded: `established` (true + you have evidence) / `consistent` (true, unevidenced) / `unsupported` / `contradicted` / `veiled` ("the archives go quiet") |
| `progress()` | free | items examined, budget left, best theory score |

Design properties:

- **Fog of war is server state, not model discipline** — per-explorer
  progress persists in `worlds/seed-N/explorations/<name>.json`; the seeker
  never sees `hidden` fields, veils, or false-rumor flags.
- **Errors are diegetic** ("no record survives of such a thing") — nothing
  leaks through error strings.
- **`delve` drives depth on demand**: exploration is what materializes new
  history, budgeted so agents must strategize about where to dig.
- **`theorize` makes it a benchmark**: ground truth is machine-readable, so
  a seeker agent's lore reconstruction is scorable (offline lexical judge, or
  Claude judge with `--model`). Score = established×3 + consistent×2 +
  veiled×1 − contradicted.
- **Two lenses**: `--role archivist` adds a `canon()` tool (full ledger) for
  GM/eval harnesses; seekers calling it are barred in-world.

`explore.py` is the same API as a plain Python class (`Exploration`), usable
without MCP.

## Guarantees

- **Genesis is byte-deterministic** per seed; **expansion skeletons are
  deterministic per node** (verified in testing: expanding `e14` on two
  divergent copies of a world yields identical children). Full-world identity
  holds when the same expansion sequence is applied.
- **Canon is enforced mechanically**: the ledger rejects events dated outside
  the world's span, participants acting after their recorded fate
  ("Mazirast cannot act in year 533: fate sealed in year 523"), duplicate
  names, and references to unknown ids. LLM output merges only through these
  validated paths — bad notes are dropped, never written.
- **LLM-optional**: every surface (describe, elaborate, ask) has a template
  fallback that obeys the same fragment/bias/veil rules.

## Files

- [`worldsim.py`](worldsim.py) — genesis sim: 5 cosmology archetypes
  (flame / sea / root / moon / song) × 3-veil mystery chains, 3 ages,
  ~25–28 events, ~13 artifacts.
- [`ledger.py`](ledger.py) — the canon fact store + validators + rendering.
- [`expand.py`](expand.py) — per-event-kind expansion templates (great war →
  battles and a champions' bargain; betrayal → the go-between and the price;
  rite → the choosing and the procession; sealing → the named dead and the
  wardenship; twilight → last audiences and the empty seat; generic →
  testimony and aftermath), plus item minting.
- [`loregen.py`](loregen.py) — style guide, three Claude Opus 4.8 surfaces
  (streamed, adaptive thinking, JSON-schema structured output), template
  fallbacks.
- [`main.py`](main.py) — CLI (`generate | deepen | ask | codex`).
- [`explore.py`](explore.py) — the agent-facing exploration API: fog-of-war
  state, leads extraction, delve resolution, and the two judges.
- [`mcp_server.py`](mcp_server.py) — FastMCP stdio wrapper over `explore.py`.
- [`worlds/`](worlds/) — committed samples (template mode; this container has
  no API key): seed-9021 is genesis-only; seed-107 has been deepened five
  times (see its nested `chronicle.md` — e.g. the great war now contains the
  battle of Haruienreach and a champions' duel that was "not fought to a
  death but to a bargain", and minted the *Torn Standard of Haruienreach*).

## Key findings / notes

- The **write-back is what makes it deep rather than improvised**: LLM
  texture becomes canon, so subsequent expansions must honor it.
- Skeleton-then-elaborate degrades gracefully: if the LLM call fails, the
  deterministic skeleton still commits, and elaboration can't corrupt canon
  because merging goes through the validators.
- Prompt-caching note for heavy use: the chronicle is rendered at the top of
  every prompt — putting a `cache_control` breakpoint after it would make
  repeated deepening cheap within the TTL.

## Next steps

- `deepen --auto N`: let the model choose the N most narratively load-bearing
  nodes to expand.
- Item re-description after deepening (an item's provenance got richer — let
  its description sharpen, as a "remembering" mechanic).
- A reconstruction validator: ask Claude to rebuild the chronicle from the
  codex alone, scoring how much truth is recoverable (lore difficulty tuning).
