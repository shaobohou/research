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

## Code Structure

```
aidanbench/
├── README.md          # This file
├── notes.md           # Progress log
├── run/
│   ├── run_benchmark.py   # Main runner script
│   ├── models.py          # Anthropic API adapter
│   └── results.json       # Raw benchmark results
└── AidanBench/        # Cloned benchmark repo (excluded from git)
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
