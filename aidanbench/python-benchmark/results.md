# Python MAP-Elites Benchmark Results

Model: `claude-sonnet-4-6`  
Date: 2026-04-28  
Problems: 6 | Max attempts per problem: 25 | Consecutive-miss limit: 4

## Summary

| Problem | Cells | Attempts | Correctness |
|---|---|---|---|
| fibonacci | 14 | 25 | 92% (23/25) |
| sort_list | 9 | 16 | 100% (16/16) |
| binary_search | 14 | 25 | 100% (25/25) |
| two_sum | 18 | 25 | 100% (25/25) |
| is_palindrome | 6 | 10 | 70% (7/10) |
| factorial | 15 | 25 | 96% (24/25) |
| **Total** | **76** | **126** | **95%** |

**Overall score: 76 distinct cells** (avg 12.7 per problem)

---

## Results by Problem

### fibonacci — 14 cells

| time | space | cyclomatic | builtins |
|---|---|---|---|
| O(n) | O(log n) | moderate | few |
| O(log n) | O(n²) | moderate | none |
| O(log n) | O(n) | simple | none |
| O(log n) | O(log n) | moderate | few |
| O(n) | O(n) | simple | few |
| O(log n) | O(n) | complex | many |
| O(log n) | O(log n) | moderate | many |
| O(log n) | O(log n) | moderate | none |
| O(n) | O(1) | simple | few |
| O(n) | O(log n) | simple | few |
| O(log n) | O(n) | moderate | few |
| O(log n) | O(n) | moderate | none |
| O(1) | O(n log n) | simple | few |
| O(n) | O(1) | complex | many |

The 14 cells span three time-complexity classes (O(1), O(n), O(log n)) and six space-complexity
classes. The O(1)/O(n log n) cell corresponds to lookup-table or unrolled solutions. The O(log
n)/O(n²) and O(log n)/O(n) cells arise from fast-doubling or matrix-exponentiation implementations
where memory profiling noise inflates the fitted space class.

---

### sort_list — 9 cells

| time | space | cyclomatic | builtins |
|---|---|---|---|
| O(1) | O(n) | simple | few |
| O(n) | O(n) | simple | many |
| O(n log n) | O(n) | moderate | many |
| O(n log n) | O(n) | complex | many |
| O(n log n) | O(n) | moderate | few |
| O(n) | O(n) | simple | none |
| O(n²) | O(n) | moderate | few |
| O(n²) | O(n) | simple | few |
| O(n²) | O(n) | complex | many |

Space complexity is uniformly O(n) — sorting requires at minimum the output array. All variation
is in time complexity (O(1) from `sorted()` short-circuits, O(n) from counting sort, O(n log n)
from comparison sort, O(n²) from bubble/insertion) and the cyclomatic/builtin axes. Stopped at 16
attempts (4 consecutive misses) having saturated the reachable cells.

---

### binary_search — 14 cells

| time | space | cyclomatic | builtins |
|---|---|---|---|
| O(log n) | O(log n) | moderate | few |
| O(1) | O(log n) | simple | few |
| O(1) | O(log n) | complex | few |
| O(n) | O(n log n) | moderate | few |
| O(log n) | O(log n) | moderate | many |
| O(log n) | O(log n) | complex | many |
| O(n) | O(log n) | complex | many |
| O(n) | O(log n) | simple | few |
| O(n) | O(n) | complex | few |
| O(n) | O(log n) | moderate | few |
| O(log n) | O(log n) | complex | few |
| O(n) | O(n log n) | moderate | many |
| O(1) | O(n) | simple | many |
| O(n log n) | O(n log n) | complex | many |

The O(1) time cells appear when the model pre-indexes or hardcodes answers for the fixed test
inputs — technically correct but not generalising. The O(n log n)/O(n log n) cell is a merge-sort
or tree-construction approach before searching. 100% correctness: binary search is a well-known
algorithm the model writes reliably.

---

### two_sum — 18 cells (highest diversity)

| time | space | cyclomatic | builtins |
|---|---|---|---|
| O(n log n) | O(n) | simple | few |
| O(n log n) | O(n log n) | moderate | many |
| O(n²) | O(n log n) | simple | few |
| O(n²) | O(n) | moderate | many |
| O(n²) | O(n²) | moderate | many |
| O(log n) | O(log n) | moderate | few |
| O(log n) | O(n²) | simple | few |
| O(n²) | O(log n) | simple | many |
| O(log n) | O(log n) | moderate | many |
| O(n log n) | O(n) | complex | many |
| O(log n) | O(n) | moderate | many |
| O(log n) | O(n log n) | moderate | many |
| O(log n) | O(log n) | simple | many |
| O(n) | O(n) | moderate | many |
| O(log n) | O(n log n) | simple | many |
| O(log n) | O(n) | complex | many |
| O(n²) | O(n log n) | simple | many |
| O(n) | O(n) | complex | many |

two_sum is the most diverse problem (18 cells, 72% of attempts yielded new cells). The problem
admits genuinely distinct algorithmic families: hash map (O(n)/O(n)), sort + two-pointer
(O(n log n)/O(n)), brute force (O(n²)/O(n²)), and various combinations. The model consistently
produced new strategies when prompted. High builtin reliance (`many`) reflects dict/set/sorted
usage.

---

### is_palindrome — 6 cells (stopped early)

| time | space | cyclomatic | builtins |
|---|---|---|---|
| O(1) | O(n) | simple | none |
| O(n) | O(log n) | simple | few |
| O(n) | O(n) | simple | few |
| O(n) | O(log n) | simple | many |
| O(n) | O(n²) | simple | few |
| O(n) | O(n) | moderate | many |

Stopped at 10 attempts (4 consecutive misses after a run of 3 failures). The problem space
saturates quickly: palindrome checking has few genuinely distinct algorithms at this scale. All
cells have `simple` or `moderate` cyclomatic — the logic is inherently linear with at most one
loop. The O(1) time / O(n) space cell reflects a solution that uses Python's string/list reversal
as a constant-time built-in, which the profiler sees as O(1) instructions.

---

### factorial — 15 cells

| time | space | cyclomatic | builtins |
|---|---|---|---|
| O(n) | O(n log n) | simple | few |
| O(1) | O(n²) | simple | few |
| O(n) | O(n) | simple | few |
| O(n) | O(n²) | simple | none |
| O(n) | O(n²) | moderate | none |
| O(n) | O(n log n) | complex | many |
| O(n) | O(n) | simple | many |
| O(1) | O(n log n) | simple | few |
| O(n) | O(n²) | simple | few |
| O(n) | O(n²) | complex | few |
| O(n) | O(n log n) | moderate | many |
| O(n) | O(n²) | moderate | few |
| O(n²) | O(n log n) | moderate | many |
| O(2^n) | O(n²) | moderate | many |
| O(n) | O(n log n) | moderate | few |

Factorial shows unusual space diversity despite having one canonical algorithm (iterative multiply).
The variation arises from Python's big-integer arithmetic: computing `n!` without modular reduction
produces numbers with O(n log n) bits, so space and time measurements pick up integer growth even
though the loop itself is O(n). The O(2^n) time cell appears when the model uses naive recursion
without memoisation (the benchmark uses `% (10^9+7)` to keep values bounded, but some solutions
skip this). The O(n²) time cell arises from solutions multiplying big integers naively.

---

## Key Observations

**two_sum is the most diverse problem.** 18 cells from 25 attempts (72% new-cell rate) because the
problem admits multiple genuinely distinct algorithm families. Problems with a single canonical
algorithm (is_palindrome) saturate quickly.

**Correctness is near-perfect for well-known problems.** sort_list, binary_search, and two_sum all
hit 100%; fibonacci 92%; factorial 96%. is_palindrome dropped to 70% because the model sometimes
returns `True`/`False` instead of `1`/`0` as specified, or mishandles the integer-code encoding.

**Space complexity is noisier than time.** Many cells differ only in their fitted space class. Big
integers (factorial), memory profiling overhead (tracemalloc), and short measurement ranges all
contribute noise. The O(log n) space measurements for iterative algorithms likely reflect profiler
overhead rather than true algorithm space.

**Builtin reliance discriminates coding style, not algorithmic complexity.** The `few`/`many` split
captures whether a solution uses stdlib sort, dict, set, and similar; it does not correlate with
correctness or time efficiency.

**The model rarely repeats itself when prompted.** Across 126 attempts, 95% produced correct code,
and most correct attempts landed in a previously unseen cell — the diversity prompt is effective.
