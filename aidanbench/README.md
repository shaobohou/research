# AidanBench: claude-sonnet-4-6 Evaluation

Evaluation of `claude-sonnet-4-6` on [AidanBench](https://github.com/AidanMcLaughlin/AidanBench), a benchmark measuring LLM creative divergence — how many unique, coherent answers a model can generate for open-ended questions.

## Summary

| Metric | Value |
|---|---|
| Model | claude-sonnet-4-6 |
| Benchmark | AidanBench (63 questions) |
| Questions answered | 22/63 |
| Questions failed (rate limit) | 41/63 |
| **Official AidanBench Score** | **5.41** |
| Avg score (completed questions only) | 15.50 |
| Total runtime | ~22 minutes |

> **Note**: 41/63 questions received no answers due to HTTP 429 rate-limiting from running 8 parallel workers. The score of 5.41 reflects 0 scores for those questions. The intrinsic per-question score (15.50) better represents actual model capability.

## How AidanBench Works

For each question, the model generates answers until:
- Coherence score drops below 15 (answer is incoherent/repetitive)
- Embedding dissimilarity score drops below 0.15 (answer too similar to previous)

The score for each question = sum of embedding dissimilarity scores of accepted answers. Final score = average across all questions.

## Results by Question

| Question | Answers | Score |
|---|---|---|
| How could we modify the rules of chess to make it more exciting for spectators? | 120 | 37.83 |
| How might we enable LLMs to spend more output tokens to get predictably better results? | 121 | 37.00 |
| What is a cause of World War 1? | 102 | 33.19 |
| How could we redesign the American education system to better prepare students for the 22nd century? | 89 | 26.93 |
| Describe a plausible alien life form that doesn't rely on carbon-based biology. | 74 | 26.58 |
| What might be an unexpected consequence of achieving nuclear fusion? | 92 | 26.01 |
| Design an original sport that combines elements of three existing sports. | 75 | 23.71 |
| Propose a solution to Los Angeles traffic. | 86 | 23.29 |
| Propose an alternative to democracy for successfully and fairly governing a country. | 67 | 20.53 |
| How might you use a brick and a blanket? | 51 | 15.22 |
| How might human evolution be affected by long term space colonization? | 35 | 14.22 |
| What might be an unexpected solution to reducing plastic waste in oceans? | 40 | 14.11 |
| What could be a novel use for blockchain technology outside of cryptocurrency? | 38 | 11.40 |
| Invent a new musical instrument and describe how it would be played. | 24 | 9.82 |
| What's one way to use oregano? | 31 | 8.99 |
| Why did Rome fall? | 11 | 3.18 |
| What architectural design features should be included in a tasteful home? | 8 | 2.01 |
| What would be the implications of a universal basic income on American society? | 6 | 1.82 |
| What activities might I include at a party for firefighters? | 6 | 1.67 |
| Why might the United States government nationalize ASI development? | 5 | 1.51 |
| Provide an explanation for Japan's Lost Decades. | 2 | 1.00 |
| How might we terraform Venus instead of Mars, and why? | 2 | 1.00 |
| *(41 questions — rate limited, 0 answers)* | 0 | 0.00 |

## Key Observations

1. **Open-ended divergent questions score highest**: Questions with many valid distinct answers (chess rule modifications, WW1 causes, education reform) allow the model to generate 70-120+ answers
2. **Narrow questions break early**: "What's one way to use oregano?" — answers quickly become repetitive despite 31 attempts
3. **Rate limiting severely impacted results**: 41/63 questions got no answers due to API 429 errors from 8-worker parallelism

---

## Major Findings

### AidanBench

**Causal plurality drives divergence more than topic breadth.**
"What is a cause of World War 1?" scored 33.19 with 102 answers — higher than "Why did Rome fall?" (3.18, 11 answers) despite similar apparent breadth. The difference: WW1 has many independent causal threads (assassination, alliances, imperialism, nationalism, mobilisation timetables…), while Rome's fall invites a single narrative that quickly becomes self-similar. Questions that are *factually open-ended* (many valid distinct causes/solutions) consistently outperform questions that are *creatively open-ended* but converge on a canonical answer.

**High answer counts do not guarantee high scores.**
The top two questions (chess rules, LLM scaling) both reached 120+ answers. Many answers are accepted but contribute small dissimilarity increments as the model exhausts genuinely novel directions. The per-answer contribution shrinks across the run — early answers contribute ~0.3–0.4 each; late answers contribute ~0.1–0.2. This means the score curve is concave: diversity is front-loaded.

**Rate limiting is the dominant confounder in this run.**
Official score 5.41 vs intrinsic 15.50 — a 2.9× gap caused entirely by 41/63 questions scoring zero due to HTTP 429 errors from 8-worker parallelism. The intrinsic score is the more meaningful number for model comparison; the official score is not usable for cross-model benchmarking without re-running with reduced parallelism.

**Narrow-domain questions hit a ceiling fast.**
"What activities might I include at a party for firefighters?" and "What's one way to use oregano?" exhaust genuine variety within 6–31 answers. The embedding dissimilarity threshold (0.15) catches near-duplicates, but even superficially different answers can be semantically close once the domain is saturated.

---

### ISA MAP-Elites (Fibonacci)

**4 distinct cells from 13 attempts; correctness rate ~54% (7/13).**
The model reliably writes correct iterative fibonacci in the custom ISA. Sub-optimal solutions (address-out-of-range, wrong off-by-one) account for most failures. Failure rate is comparable to Python despite the custom language — the ISA's MIPS/RISC-V-style syntax is familiar enough that the model rarely generates syntactically invalid programs.

**The cyclomatic axis cleanly separates algorithm families.**
`simple` (cc ≤ 3) captures pure iterative loops with one comparison. `moderate` (cc 4–7) captures fast-doubling and matrix-exponentiation approaches with multiple conditional branches. This axis turned out more discriminating than register pressure, which collapsed to `r0-r7` for every solution (all fibonacci implementations naturally use 4–6 registers).

**Program size and cyclomatic are genuinely independent.**
The `small/simple` cell (17 instructions, 1 branch) and `medium/moderate` cell (27 instructions, 4–5 branches) are both O(n)/O(1) — same time and space complexity, different structural character. Without both axes these would be the same cell.

**The O(log n) cell requires correct manual stack management.**
The `('O(log n)', 'O(log n)', 'large', 'moderate')` cell — matrix exponentiation — needs STOR/LOAD for a 2×2 matrix scratch area since the ISA has no CALL/RET. The model successfully produced this (insn_count grows by ~30 per input doubling at large n, consistent with O(log n)). The memory high-water mark grows slowly (6→10 addresses as n goes 100→10000) confirming O(log n) space from the recursion-depth-equivalent stack.

**Binary search was removed: O(n) I/O loading collapses diversity.**
Any correct binary-search implementation must read all n input elements before searching — making time complexity O(n) and mem_hwm O(n) for all correct solutions regardless of the search algorithm. All valid solutions land in the same cell, so the problem contributes nothing to MAP-Elites diversity.

**The ISA measurement environment is cleaner than Python's.**
Instruction counts are exact and deterministic (no OS scheduling noise, no GC, no big-integer arithmetic growth). The R² curve-fitting converges faster and more reliably than wall-clock timing. Fibonacci at n=10,000 produces exactly 100,006 instructions for a simple iterative loop — the count is a pure function of the algorithm.

## Code Structure

```
aidanbench/
├── README.md              # This file
├── notes.md               # AidanBench run log
├── run/
│   ├── run_benchmark.py   # AidanBench runner script
│   ├── models.py          # Anthropic API adapter (shared)
│   └── results.json       # AidanBench raw results
├── python-benchmark/      # MAP-Elites benchmark: Python as target language
│   ├── benchmark.py       # Runner (prompts model, fills MAP-Elites archive)
│   ├── features.py        # Feature extraction (time, space, cyclomatic, builtin)
│   ├── problems.py        # Problem definitions (fibonacci, sort, search, …)
│   ├── python-spec.md     # Design specification
│   └── notes.md           # Implementation notes
├── isa-benchmark/         # MAP-Elites benchmark: custom ISA as target language
│   ├── benchmark.py       # Runner
│   ├── features.py        # Feature extraction (time, space, program size, cyclomatic)
│   ├── problems.py        # Problem definitions (fibonacci; more planned)
│   ├── interpreter.py     # ISA interpreter with insn_count and mem_hwm tracking
│   ├── test_interpreter.py # 146-test suite for the interpreter
│   ├── MANUAL.md          # Programmer's manual for the ISA
│   ├── isa-spec.md        # Design specification and feature space
│   ├── isa-options.md     # Comparison of ISA options considered
│   └── results.json       # Latest benchmark results
└── AidanBench/            # Cloned benchmark repo (excluded from git)
```

## Running

```bash
cd run
uv run run_benchmark.py
# or
python3 run_benchmark.py
```

Requires `ANTHROPIC_API_KEY` env var set.

## Next Steps

- Re-run with 2 workers + retry logic to avoid rate limiting and complete all 63 questions
- Compare scores against other Claude models (opus-4-6, haiku-4-5)
