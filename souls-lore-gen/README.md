# souls-lore-gen

A Dwarf Fortress-style procedural history generator whose player-facing output
is **Dark Souls / Elden Ring style item descriptions** — the true history is
simulated, then deliberately shattered into incomplete, biased fragments that
must be triangulated across items.

## How it works

```
seed ──▶ worldsim.py ──▶ true chronicle (gods, ages, wars, betrayals,
              │           artifacts with provenance, one hidden mystery)
              ▼
         knowledge packets   each item gets: a few true facts, a faction
              │              bias, sometimes a false rumor, and (rarely)
              ▼              permission to *hint* at the mystery
         loregen.py ──▶ Claude Opus 4.8 (one batched, schema-constrained
              │          call) or a deterministic template fallback
              ▼
         codex.md  (the deliverable — item lore, no spoilers)
         chronicle.md  (ground truth, for the curious / for debugging)
```

The design mirrors why Souls lore feels the way it does:

- **Simulate first, narrate second** (the DF move): every item description is
  backed by real events with real causality, so fragments cross-reference
  correctly — the same betrayal shows up in a crown, a blade, and a hanged
  traitor's fate.
- **Knowledge packets**: an item only "knows" the events in its provenance
  chain, plus a hedged glimpse (50% chance per secret) of any hidden layer.
- **Bias**: the church relic frames loss as trial; the cult trinket blames
  the gods (and, Souls-classically, the heretics are *nearer* the truth);
  the peddler's item gets names wrong.
- **False rumors**: ~35% of items embed one confidently wrong belief, unmarked.
- **The central mystery is never stated**: 2–3 items may gesture at it in a
  single deniable clause. The chronicle prints it under a spoiler warning.

## Usage

```sh
# Full experience — needs ANTHROPIC_API_KEY (or an `ant auth login` profile)
uv run main.py --seed 107 --items 14

# Offline demo — deterministic template prose, no key needed
uv run main.py --seed 107 --no-llm
```

Outputs land in `worlds/seed-<N>/`: `codex.md`, `chronicle.md`, `world.json`.
Same seed ⇒ byte-identical world (verified), so you can compare the template
and LLM renderings of the *same* history.

## Files

- [`worldsim.py`](worldsim.py) — seeded history sim: 5 cosmology archetypes
  (flame / sea / root / moon / song), 3 ages, ~28 events, ~12 named figures,
  ~13 artifacts per world.
- [`loregen.py`](loregen.py) — style guide + one streamed
  `claude-opus-4-8` call with adaptive thinking and a `json_schema`
  structured output; template fallback mirrors the same constraints.
- [`main.py`](main.py) — CLI.
- [`worlds/`](worlds/) — committed sample output (template mode; this
  container has no API key). Example fragment, seed 9021 (flame world):

  > **Cinder of Tormund** — A catalyst attuned to the old gift.
  > The Cinder of Tormund was wrought as regalia of Tormund's throne. It
  > hums, faintly, as if answering something far below. What became of it
  > after is not written.

## Key findings / notes

- One **batched** LLM call (whole chronicle + all items in context) beats
  per-item calls: contradictions stay deliberate, names stay consistent, and
  the epigraph can echo the item set. Structured output keeps parsing safe.
- The **hidden layer** (per-event `hidden:` truths + one world-level mystery)
  is what creates the "archaeology" feel — without facts the items *withhold*,
  descriptions read as flavor text rather than evidence.
- Template mode is a useful floor: it proves the fragment/bias mechanics work
  without any model, and gives a fixed baseline to judge LLM prose against.

## Next steps

- Feed `world.json` back in for **NPC dialogue** and **area descriptions**
  drawn from the same knowledge-packet mechanic.
- Multi-generation item drift: re-describe the same item "an age later" with
  degraded knowledge.
- A small validator that asks Claude to *reconstruct* the chronicle from the
  codex alone, scoring how much of the true history is recoverable (lore
  difficulty tuning).
