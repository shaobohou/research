# AidanBench on claude-sonnet-4-6: Notes

## Objective
Run AidanBench to evaluate claude-sonnet-4-6's creative divergence and answer diversity.

## Setup
- Cloned AidanBench into `AidanBench/`
- Created custom `run/` directory with:
  - `models.py`: Custom model adapter using Anthropic API (maps `anthropic/claude-sonnet-4` → `claude-sonnet-4-6`)
  - `run_benchmark.py`: Runner script with 8 parallel workers

## Execution
- Command: `cd run && python3 run_benchmark.py > /tmp/benchmark_run2.log 2>&1 &`
- Total runtime: ~1343 seconds (~22 minutes)
- Parallelism: 8 workers

## Results
- Total questions in benchmark: 63
- Questions with answers: 22/63 (41 failed due to HTTP 429 rate limiting)
- **Official AidanBench score (avg embedding dissimilarity across all 63 questions): 5.41**
- Score over completed questions only: 341.01 / 22 = 15.50

## Issues Encountered
- **Rate limiting (HTTP 429)**: Heavy parallel usage caused 41/63 questions to fail with 429 errors
  - The 8-worker parallel approach hit API rate limits
  - Completed questions mostly succeeded on the first attempt before rate limits kicked in
  - A retry-with-backoff strategy or reduced parallelism would help

## Key Findings
- Questions requiring open-ended creative divergence (chess rules, LLM token usage, WW1 causes) scored highest
- Top score: "How could we modify the rules of chess to make it more exciting for spectators?" → 37.83
- The model generated 120-121 answers before breaking on top questions
- Simple/narrow questions (oregano uses, firefighter party activities) broke earlier

## Next Steps
- Re-run with reduced parallelism (2-4 workers) and retry logic to avoid 429s
- Compare against other models (claude-opus-4-6, claude-haiku-4-5)
