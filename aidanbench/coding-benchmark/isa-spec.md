# Custom ISA: Specification and MAP-Elites Benchmark Plan

---

## 1. Machine State

| Component | Description |
|-----------|-------------|
| Registers | R0–R7, 32-bit signed integers, initialised to 0 |
| Memory    | Flat array of 32-bit signed integers, addresses 0–65535, initialised to 0 |
| PC        | Program counter, starts at first instruction |
| Input     | Tape of integers consumed one at a time by IN |
| Output    | Sequence of integers produced by OUT |

Two instrumentation counters maintained by the interpreter (invisible to programs):
- **insn_count** — incremented on every executed instruction
- **mem_hwm** — high-water mark: max memory address written during execution

---

## 2. Instruction Set

`dst` must be a register. `src` may be a register or an integer literal.
`base` is a register; `off` is an integer literal (default 0, written `[base]`).
`label` is a symbolic name defined by `label:` in the source.

### Arithmetic

```
MOV  dst, src          # dst = src
ADD  dst, src          # dst += src
SUB  dst, src          # dst -= src
MUL  dst, src          # dst *= src
DIV  dst, src          # dst = int(dst / src)  (truncates toward zero)
MOD  dst, src          # dst = dst % src       (sign follows dividend)
```

### Memory

```
LOAD dst, [base+off]   # dst = mem[base + off]
STOR src, [base+off]   # mem[base + off] = src
```

`off` may be omitted: `[base]` means `[base+0]`.

### Control Flow

```
JMP  label             # PC = label (unconditional)
JZ   reg, label        # if reg == 0: PC = label
JNZ  reg, label        # if reg != 0: PC = label
JLT  reg, src, label   # if reg < src: PC = label
JLE  reg, src, label   # if reg <= src: PC = label
```

All comparisons derived from these two: `JGT a b L` → `JLT b a L`;
`JGE a b L` → `JLE b a L`; `JEQ a b L` → `SUB tmp a; SUB tmp b... ` etc.
These are macros the model may use; the interpreter expands them.

### I/O

```
IN   dst               # dst = next integer from input tape
OUT  src               # append src to output
HALT                   # stop execution
```

### Macros (syntactic sugar, expanded before execution)

```
JGT  reg, src, label   # expands to: JLT src, reg, label
JGE  reg, src, label   # expands to: JLE src, reg, label
INC  reg               # expands to: ADD reg, 1
DEC  reg               # expands to: SUB reg, 1
CLR  reg               # expands to: MOV reg, 0
```

---

## 3. Calling Conventions

Input is passed entirely via IN; output via OUT before HALT.

**Scalars**: single IN at the start.

**Arrays**: first IN reads the length n, then n INs read the elements.

**Multiple inputs**: read in order (e.g. binary search: IN length, then n
elements, then the target).

**Return value**: one or more OUTs before HALT. For boolean problems, OUT 1
(true) or OUT 0 (false).

---

## 4. Benchmark Problems (ISA edition)

| Problem | Input format | Expected output |
|---------|-------------|-----------------|
| fibonacci | n | fib(n) % (10^9+7) |
| sort_list | n, then n integers | n integers in sorted order |
| binary_search | n, n integers (sorted), target | index or -1 |
| two_sum | n, n integers, target | i, j (two lines) |
| is_palindrome | n, then n integers (char codes) | 1 or 0 |
| factorial | n | n! % (10^9+7) |

For `sort_list` the output is n integers emitted via n OUT instructions.
For `is_palindrome` the string is encoded as a sequence of integer char codes
to avoid string I/O.

---

## 5. Feature Space

### 5.1 Empirical Features (run-time, fitted via R²)

Run the program on inputs of increasing size n. Fit the resulting series to
complexity classes using the same least-squares R² method as the Python
benchmark.

**Time complexity** — series: `insn_count(n₁), insn_count(n₂), ...`
Classes: O(1), O(log n), O(n), O(n log n), O(n²), O(2^n)

Cleaner than Python wall-clock: exact, deterministic, no OS noise.

**Space complexity** — series: `mem_hwm(n₁), mem_hwm(n₂), ...`
Classes: O(1), O(log n), O(n), O(n²)

Pure algorithm space — no allocator overhead, no GC, no object headers.
Programs that use only registers have mem_hwm = 0 across all sizes → O(1).

### 5.2 Static Features (source analysis)

**Cyclomatic complexity** — count branch instructions in source:
JMP, JZ, JNZ, JLT, JLE (and their macro expansions).
Bins: simple (1–3), moderate (4–8), complex (9+).

Unlike Python, every branch is explicit and visible — no hidden control flow
from builtins or comprehensions.

**Register pressure** — highest register index referenced in source:
- few: only R0–R1
- some: up to R3
- many: R4 or higher

Captures how heavily the solution exploits the register file. A low-register
solution must spill to memory or restructure the algorithm.

**Program length** — total instruction lines in source (after macro expansion):
- tiny: ≤ 15
- short: 16–40
- medium: 41–80
- long: > 80

### 5.3 Default Cell Key (5 dimensions)

```
(time_complexity, space_complexity, cyclomatic, register_pressure, program_length)
```

Replaces Python's `builtin_reliance` (always zero in assembly) with
`register_pressure` and `program_length`, both of which vary meaningfully
across ISA solutions.

---

## 6. Constraints

Constraints are hard limits enforced by the interpreter. A solution that
violates any active constraint is marked incorrect (regardless of output).

### 6.1 Register Budget

Restrict available registers to a prefix of R0–Rk.

| Budget | Registers | Effect |
|--------|-----------|--------|
| 2 | R0, R1 | Forces heavy memory use; no room for loop counter + two accumulators simultaneously |
| 4 | R0–R3 | Comfortable for simple algorithms; matrix multiply requires spilling |
| 8 | R0–R7 | Full machine (default) |

**As a feature axis**: "registers used" (peak register index touched at runtime)
varies even without a hard budget, becoming a continuous measure of register
economy.

### 6.2 Memory Budget

Cap the maximum writable address.

| Budget | Cells | Effect |
|--------|-------|--------|
| 0 | none | Register-only programs; forces streaming O(1)-space algorithms |
| 16 | tiny scratch | Allows small temporaries; no O(n) DP tables for n > 16 |
| 256 | small | DP tables for small n; forces in-place sorting for large n |
| unlimited | full | Default |

**Most interesting pairing**: `memory_budget=0` forces every algorithm to be
register-only, making space always O(1) and shifting all variation to time
complexity and cyclomatic.

### 6.3 Program Size Budget

Cap total instructions in source.

| Budget | Lines | Effect |
|--------|-------|--------|
| 15 | TIS-100 node | Extreme compression; only the simplest algorithms fit |
| 32 | tight | Iterative fibonacci fits; matrix exp requires ingenuity |
| 64 | moderate | All benchmark problems solvable; multiple strategies viable |
| unlimited | default | No constraint |

Forces algorithmic compression: a model cannot solve binary search with a
linear scan when constrained to 20 instructions.

### 6.4 Instruction Whitelist

Restrict which opcodes may appear in source.

| Profile | Disallowed | Effect |
|---------|-----------|--------|
| full | — | Default, all 15 instructions available |
| no-mul | MUL, DIV, MOD | Multiply must be an add-loop; changes time complexity of solutions that naively use MUL |
| minimal | MUL, DIV, MOD, LOAD, STOR | Register-only + basic arithmetic; closest to a pure function |
| branches-only | MUL, DIV, MOD, LOAD, STOR, macros | Turing complete but very constrained |

`no-mul` is the most interesting: sorting and fibonacci have obvious MUL-free
forms, but two_sum (hash map) requires rethinking entirely.

### 6.5 Constraints as Feature Axes

Rather than imposing constraints as hard limits, they can be *measured* as
additional axes, letting MAP-Elites reward solutions that achieve diversity
along constraint dimensions without enforcing them:

| Axis | Values | What it captures |
|------|--------|-----------------|
| peak_registers_used | 1–2, 3–4, 5–8 | Register economy |
| memory_cells_used | 0, 1–16, 17–256, 256+ | Space strategy |
| distinct_opcodes | ≤4, 5–8, 9+ | Instruction variety |
| source_lines | tiny, short, medium, long | Compression |

A solution that sorts a list using only R0–R1 and no memory occupies a
genuinely different cell from one that uses 6 registers and a scratch buffer,
even if both are O(n log n) time.

---

## 7. Full Feature Space Summary

### Recommended default (5 axes, no hard constraints)

| Axis | Source | Values |
|------|--------|--------|
| time_complexity | empirical (insn_count fit) | O(1) O(log n) O(n) O(n log n) O(n²) O(2^n) |
| space_complexity | empirical (mem_hwm fit) | O(1) O(log n) O(n) O(n²) |
| cyclomatic | static (branch count) | simple moderate complex |
| register_pressure | static (max reg index) | few some many |
| program_length | static (line count) | tiny short medium long |

Maximum possible cells per problem: 6 × 4 × 3 × 3 × 4 = **864**
Realistically reachable: 20–40 (most complexity combinations are
algorithmically impossible or equivalent).

### Extended (add constraint-derived axes)

Add `memory_cells_used` and `distinct_opcodes` for a 7-axis space.
Maximum cells: 864 × 4 × 3 = **10,368** — mostly empty, but richer
for problems like sort where many strategies exist.

---

## 8. Implementation Plan

### Phase 1 — Interpreter

`isa/interpreter.py` (~100 lines)
- Parse assembly text (labels, instructions, operands)
- Execute with insn_count and mem_hwm tracking
- Enforce register/memory/size/whitelist constraints
- Run program on a list of integer inputs, return list of integer outputs

### Phase 2 — Feature Extraction

Adapt `features.py`:
- Replace Python subprocess runner with ISA interpreter calls
- Static analysis of assembly source: count branches, max register index,
  source lines, distinct opcodes
- Same R² fitting for time and space complexity series

### Phase 3 — Problem Definitions

Adapt `problems.py`:
- New descriptions with ISA input/output format
- `size_input(n)` returns integer list (not Python args tuple)
- `test_cases`: list of (input_integers, expected_output_integers)

### Phase 4 — Benchmark Runner

Adapt `benchmark.py`:
- Prompt includes full ISA spec
- Extract assembly code from response (between code fences or XML tags)
- Correctness check runs program on test_case inputs, compares output list
- Same MAP-Elites archive loop

### Phase 5 — Constraint Variants

Add a `constraints` dict to each problem run:
```python
{"register_budget": 4, "memory_budget": 64, "whitelist": "no-mul"}
```
The interpreter enforces these; solutions that violate are scored as incorrect.
Run the same problem multiple times under different constraint profiles to
explore constraint-induced diversity.

---

## 9. Example: Fibonacci Feature Space

Expected distinct cells across algorithm families (no constraints):

| Algorithm | time | space | cyclomatic | reg_pressure | prog_len |
|-----------|------|-------|------------|--------------|----------|
| iterative | O(n) | O(1) | simple | few | tiny |
| dp in memory | O(n) | O(n) | simple | some | short |
| matrix exp | O(log n) | O(1) | moderate | many | medium |
| naive recursive* | O(2^n) | O(n) | moderate | some | short |
| unrolled (fixed n) | O(1) | O(1) | simple | few | long |

*Requires manual stack management via STOR/LOAD since ISA has no CALL/RET.

5 distinct cells — same as Python. But under `memory_budget=0`:
- dp in memory and naive recursive become *impossible* (need memory for table/stack)
- Only iterative, matrix exp, and unrolled survive
- A 2-cell (or 3-cell) space with constraint-induced pruning

This is the TIS-100 insight applied systematically: constraints don't just
limit, they *redirect* diversity into dimensions the unconstrained space misses.
