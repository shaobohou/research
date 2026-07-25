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
# All prose is written by Claude — set ANTHROPIC_API_KEY, or `ant auth login`.
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
enforces the epistemic boundary. The loop is spatial: chart a map, walk it,
study what you find, and venture theories no one will confirm.

| tool | cost | what it does |
|---|---|---|
| `survey()` | free | your **charted map**: where you stand, places known (walked vs only heard of), budget. *Not* a catalogue — you learn a place's relics only by going there |
| `look()` | free | what lies where you stand: relics here **with how each was found**, and the ways onward |
| `travel(place)` | 1 step | walk to a place you've heard of (returning is free); reveals its relics and neighbours |
| `examine(item)` | free | a relic you stand beside or have found: description, **how it lies**, and leads (names it mentions) |
| `ask(question)` | 1 ask | an in-world fragment, from canon, never the veils |
| `delve(target)` | 1 delve | dig into a lead: expands the world behind it, returning new accounts, sometimes **new relics**, and any **new ground** they name (added to your map) |
| `theorize(claims)` | free | **purist mode (default):** a fellow antiquary's in-world *reaction* — a nod, a doubt, or a **silence** where you touched a veil. Never a verdict, never a score |
| `progress()` / `compendium()` | free | status; and "The Book of Found Things" (also `uv run main.py lore --seed N --explorer NAME`) |

Two design commitments make this feel like Elden Ring rather than a wiki:

- **Space (the *where* is a clue).** Places are entities; every relic lies
  *somewhere*, and you discover a place's relics only by `travel`-ing there,
  spending from a step budget. Each relic carries a **placement line** — "found
  at the foot of a throne, beneath the dust of the banners" — a sim-controlled
  evidence channel independent of its description. A region you never walk to
  is a history you never learn (the seed-5 journal walks past an entire
  kingdom's betrayal for want of one road). `delve` forges new geography, so
  digging literally opens the map.
- **Purist mode (the world never confirms you).** By default `theorize`
  returns an antiquary's reaction, not a verdict — agreement on what you can
  support, doubt on what you overreach, and **silence** on anything that
  touches a veil. That silence is the only confirmation of hidden truth you
  ever get: directional, deniable, unscored — exactly how an ER NPC who
  changes the subject tells you you've found something.

Under it all the ground truth is still machine-readable, so the system
doubles as a **benchmark**: run the server with `--benchmark` (or construct
`Exploration(..., purist=False)`) and `theorize` returns graded verdicts
(`established`/`consistent`/`unsupported`/`contradicted`/`veiled`, scored
3/2/0/−1/+1) for automated scoring — a mode meant for eval harnesses, never
shown to seekers. `--role archivist` additionally exposes `canon()`.

- **Fog of war is server state, not model discipline** — per-explorer
  progress (location, map, finds) persists in
  `worlds/seed-N/explorations/<name>.json`; the seeker never sees `hidden`
  fields, veils, or false-rumor flags.
- **Errors are diegetic** ("no road you know leads there") — nothing leaks
  through error strings.

`explore.py` is the same API as a plain Python class (`Exploration`), usable
without MCP. Geography is derived idempotently by `ensure_geography`, so old
worlds migrate on first load.

## Guarantees

- **Genesis is byte-deterministic** per seed; **expansion skeletons are
  deterministic per node** (verified in testing: expanding `e14` on two
  divergent copies of a world yields identical children). Full-world identity
  holds when the same expansion sequence is applied.
- **Invariants are checked, not assumed**: `uv run selfcheck.py` runs ~6,700
  assertions over every committed world — structural (references resolve,
  depths/years coherent, geography complete), causal (no figure *acts* after
  their recorded fate), and epistemic (**no veil text ever appears in a
  world-authored surface** — descriptions, placements, accounts, codex, ask
  fragments; a compendium may quote a veil only inside the seeker's own
  claims).
- **Canon is enforced mechanically**: the ledger rejects events dated outside
  the world's span, participants acting after their recorded fate
  ("Mazirast cannot act in year 533: fate sealed in year 523"), duplicate
  names, and references to unknown ids. LLM output merges only through these
  validated paths — bad notes are dropped, never written.
- **Always LLM-backed**: there is no template writer and no offline mode.
  Every surface (describe, elaborate, ask, judge) goes to Claude; without
  credentials the tool stops with one line rather than degrading to worse
  prose. The *facts* are still pure simulation — deterministic per seed — so
  a failed call costs prose, never canon.

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
  (streamed, adaptive thinking, JSON-schema structured output), plus a
  repair pass when the model omits an item.
- [`main.py`](main.py) — CLI (`generate | deepen | ask | codex`).
- [`explore.py`](explore.py) — the agent-facing exploration API: spatial
  fog-of-war state, travel/adjacency, placement-as-evidence, delve
  resolution, and purist-reception vs benchmark-verdict theorizing.
- [`mcp_server.py`](mcp_server.py) — FastMCP stdio wrapper over `explore.py`.
- [`selfcheck.py`](selfcheck.py) — invariant checker over every world
  (structural / causal / **epistemic**); non-zero exit on failure, so it runs
  as a test: `uv run selfcheck.py`.
- [`demos.py`](demos.py) — the documented runs as reproducible code.
- Documented playthroughs:
  [`worlds/seed-7/full-walkthrough.md`](worlds/seed-7/full-walkthrough.md) — a
  complete, literal transcript (every tool call + raw output, empty state to
  final theory);
  [`worlds/seed-5/exploration-journal.md`](worlds/seed-5/exploration-journal.md)
  — a narrated spatial + purist run;
  [`worlds/seed-9/exploration-journal.md`](worlds/seed-9/exploration-journal.md)
  — the earlier catalogue-era run;
  [`worlds/seed-314/walkthrough-100steps.md`](worlds/seed-314/walkthrough-100steps.md)
  — a large-budget run (100 steps) showing delving grow the map 15→96 places.

All four documented runs are **reproducible**, not hand-made:
`uv run demos.py all` regenerates their worlds from seed, replays the same
seeker actions, and rewrites the reports — so the committed documents stay
true after any change to the generator.
- [`worlds/`](worlds/) — committed samples. **Their prose was written by the
  since-removed template writer**, so it reads plainer than a real run; the
  ledgers (events, places, provenance, veils) are pure simulation and remain
  exactly what a live run reproduces. Re-run `uv run demos.py all` with
  credentials to rewrite the prose from the same facts. seed-9021 is genesis-only; seed-107 has been deepened five
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
