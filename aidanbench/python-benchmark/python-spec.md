# Python as Target Language: Specification and MAP-Elites Benchmark Plan

---

## 1. Machine Model

Standard CPython 3.11+. No sandboxing beyond subprocess isolation. Solutions
run in a fresh process per measurement to avoid state leakage.

Solutions must define a function named `solve` with the signature given in the
problem. Any imports must appear at module level above or inside the function.

---

## 2. Benchmark Problems

| Problem | Signature | Notes |
|---------|-----------|-------|
| fibonacci | `solve(n: int) -> int` | Returns fib(n) % (10^9+7) to avoid big-integer arithmetic |
| sort_list | `solve(lst: list) -> list` | Return new sorted list |
| binary_search | `solve(arr: list, target: int) -> int` | Return index or -1 |
| two_sum | `solve(nums: list, target: int) -> list` | Return [i, j] with i < j |
| is_palindrome | `solve(s: str) -> bool` | True if s == reverse(s) |
| factorial | `solve(n: int) -> int` | Returns n! % (10^9+7) |

Correctness is checked by running the solution against a fixed test case list
in a subprocess and comparing return values.

---

## 3. Feature Space

### 3.1 Empirical Features (run-time, fitted via R²)

Run the solution on inputs of increasing size n. Each measurement uses a
separate run within the same subprocess: timing (uninstrumented), memory
(tracemalloc), and instruction count (sys.settrace) are kept separate so
tracer overhead does not corrupt timing.

**Time complexity** (default) — series: `insn_count(n₁), insn_count(n₂), ...`

Uses `sys.settrace` to count line-event callbacks — deterministic, no clock
noise. The series is fitted to complexity classes via least-squares R².

**Time complexity (timing variant)** — series: `wall_time(n₁), ...`

`timeit` with auto-scaling repetitions (doubles until total > 1ms). Stored
alongside instruction-count classification; selectable via
`cell_key(features, use_timing=True)`. Less reliable than instruction count
for Python due to big-integer arithmetic and GC noise.

**Space complexity** — series: `tracemalloc_peak(n₁), ...`

Peak memory allocation during a single `solve(input)` call. Note: Python
object headers and interpreter overhead appear in measurements. Big-integer
growth is mitigated by using modular arithmetic in problems where intermediate
values would otherwise grow unboundedly.

Complexity classes for both time and space:
`O(1), O(log n), O(n), O(n log n), O(n²), O(2^n)`

For space, O(2^n) is only returned on subprocess timeout.

### 3.2 Static Features (AST analysis)

**Cyclomatic complexity** — 1 + count of decision nodes in the AST:
`ast.If`, `ast.IfExp`, `ast.For`, `ast.While`, `ast.ExceptHandler`,
`ast.With`, `ast.Assert`, plus comprehension `if` clauses.

Bins: simple (1–3), moderate (4–7), complex (8+).

**Builtin reliance** — count of calls to Python built-in functions and common
stdlib callables used as bare names or as method calls:

- Bare-name calls matched against `PYTHON_BUILTINS`: `len`, `range`, `sorted`,
  `sum`, `map`, `filter`, `zip`, `enumerate`, `lru_cache`, `reduce`,
  `heappush`, `bisect`, `defaultdict`, `Counter`, etc.
- Method calls matched against `STDLIB_ATTRS`: `.sort()`, `.append()`,
  `.join()`, `.split()`, `.items()`, `.get()`, `.sqrt()`, etc.
- Comprehensions count as one implicit call each.

Bins: none (0), few (1–3), many (4+).

### 3.3 Default Cell Key (4 dimensions)

```python
cell_key(features) -> (time_complexity, space_complexity, cyclomatic, builtin_reliance)
```

`use_timing=True` selects the wall-clock time classification instead of
instruction-count.

### 3.4 Raw Data Stored per Solution

```python
{
  "time_complexity":        str,   # insn-count fit
  "time_complexity_timing": str,   # wall-clock fit
  "space_complexity":       str,
  "cyclomatic":             str,   # binned
  "builtin_reliance":       str,   # binned
  "cyclomatic_raw":         int,
  "builtin_raw":            int,
  "raw_times":              list[float],
  "raw_mems":               list[int],
  "raw_insns":              list[int],
}
```

---

## 4. Measurement Details

### lru_cache / memoization

`sys.settrace` caches are cleared between measurement runs via
`_clear_caches()`, which calls `cache_clear()` on any callable in the
subprocess globals that exposes it. This ensures memoised solutions are
measured cold at each input size, not warmed by the previous size's run.

### Recursion limit

Set to `max(sizes) * 2` in the measurement subprocess, so deeply recursive
solutions (e.g. memoised fibonacci at n=10000) are not falsely classified
as O(2^n) due to a RecursionError.

### Input sizes

Each problem has a `sizes` list tuned so that:
- The range is wide enough to distinguish O(log n) from O(n) from O(n²)
- The largest size does not trigger big-integer blowup
- O(2^n) solutions time out before the last few sizes (classified via timeout)

| Problem | Sizes |
|---------|-------|
| fibonacci | [100, 500, 1000, 2000, 5000, 10000] |
| sort_list | [100, 200, 400, 800, 1600, 3200] |
| binary_search | [100, 500, 1000, 5000, 10000, 50000] |
| two_sum | [100, 200, 400, 800, 1600, 3200] |
| is_palindrome | [100, 500, 1000, 5000, 10000, 50000] |
| factorial | [50, 100, 200, 400, 800, 1000] |

---

## 5. Potential Constraints

Python does not enforce hard constraints the way an ISA interpreter does, but
soft constraints can be communicated in the prompt and verified statically
or at runtime.

### 5.1 No Built-ins

Prompt instructs the model not to use any stdlib imports or built-in
functions. Verified statically: if `builtin_raw > 0`, the solution is
rejected.

Effect: `sorted()` becomes a manual sort; `sum()` becomes a loop;
`lru_cache` becomes a hand-written dict. Forces lower-level implementations
that vary more in structure.

### 5.2 No Loops (Recursion Only)

Prompt forbids `for` and `while`. Verified via AST: reject if any
`ast.For` or `ast.While` node is present.

Effect: iterative fibonacci becomes recursive or functional (`reduce`).
Every O(n) algorithm must be expressed as recursion, surfacing stack-depth
as a space feature.

### 5.3 One-liner

Prompt requires the entire function body to be a single `return` expression.
Verified via AST: function body must be exactly one `ast.Return` node.

Effect: forces functional style — comprehensions, `map`/`filter`/`reduce`,
nested ternaries. High cyclomatic complexity packed into one line.

### 5.4 No Recursion

Prompt forbids recursive calls. Verified via AST: no `ast.Call` whose
function name matches `solve` (or any function defined in the solution that
calls itself). Forces iterative solutions; eliminates memoised recursion.

### 5.5 Constraints as Feature Axes

Rather than hard-rejecting, constraints can be *measured* and added as axes:

| Axis | Values | Derived from |
|------|--------|-------------|
| uses_recursion | yes / no | AST: any self-call |
| uses_loops | yes / no | AST: For or While nodes |
| import_count | none / few / many | AST: Import nodes |
| function_count | 1 / 2–3 / 4+ | AST: FunctionDef nodes |

These capture structural diversity without hard-rejecting solutions.

---

## 6. Feature Space Summary

### Default (4 axes)

| Axis | Source | Values |
|------|--------|--------|
| time_complexity | empirical (insn_count fit) | 6 classes |
| space_complexity | empirical (tracemalloc fit) | 6 classes |
| cyclomatic | static AST | simple / moderate / complex |
| builtin_reliance | static AST | none / few / many |

Maximum possible cells per problem: 6 × 6 × 3 × 3 = **324**
Realistically reachable: 10–20.

### Extended (add constraint-derived axes)

Add `uses_recursion` and `function_count` for a 6-axis space.
Maximum cells: 216 × 2 × 3 = **1,296**.

---

## 7. Known Limitations

**Big-integer arithmetic** — Python integers grow unboundedly. Fibonacci and
factorial use modular arithmetic (`% (10^9+7)`) to bound intermediate values.
Other problems (sorting, binary search) use bounded integers in test inputs.
Without this, timing and space measurements reflect integer size growth
rather than algorithmic complexity.

**sys.settrace overhead** — The instruction-count run is 5–10× slower than
the uninstrumented run. This is why timing and instruction-count runs are
kept separate. The overhead does not affect the count itself.

**Builtin reliance undercounts delegation** — `sorted([...])` counts as one
call but hides O(n log n) work inside C. The static count measures how much
the solution delegates to the standard library, not the work that delegation
performs. This is intentional: it captures solution strategy, not runtime.

**Space measurement includes Python overhead** — `tracemalloc` sees all heap
allocations including temporary objects, list resizing, and integer caching.
O(1)-space algorithms may appear O(log n) due to constant-factor allocations
at small n. This is a known limitation; the R² fit typically still finds the
correct asymptotic class at large n.

---

## 8. Implementation Status

| Component | File | Status |
|-----------|------|--------|
| Feature extraction | `features.py` | Complete |
| Problem definitions | `problems.py` | Complete |
| Benchmark runner | `benchmark.py` | Complete |
| Results storage | `results.json` | Not yet run |
