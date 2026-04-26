# ISA Options for MAP-Elites Coding Benchmark

The goal: an instruction set that LLMs can write programs in, that we can
interpret easily, and that supports the benchmark problems (fibonacci, sort,
binary search, two_sum, palindrome, factorial).

---

## Option 1: SUBLEQ (One-Instruction ISA)

One instruction: `SUBLEQ a b c`

```
mem[b] -= mem[a]
if mem[b] <= 0: jump to c
```

Memory is a flat array of integers. Everything is encoded in terms of this
single operation.

**Fibonacci in SUBLEQ** (sketch — 20+ instructions for a trivial loop):
```
# To copy A to B: SUBLEQ B B *+1 ; SUBLEQ A tmp *+1 ; SUBLEQ tmp B *+1
# To add A to B:  SUBLEQ neg_A B *+1  (where neg_A holds -A)
# Conditional:    SUBLEQ counter counter c  checks counter <= 0
```

### Pros
- Mathematically elegant — provably Turing complete with one instruction.
- Trivial interpreter (~10 lines of Python).
- Feature space is degenerate: cyclomatic complexity is always flat
  (every SUBLEQ is a potential branch), builtin reliance is always zero.

### Cons
- Models cannot reliably write SUBLEQ. It requires encoding every operation
  as a sequence of subtracts, which is error-prone even for humans.
- Correctness rate in practice: very low (< 5% expected).
- All programs look structurally identical — the feature axes (cyclomatic,
  builtin) carry no signal.
- Debugging is nearly impossible.

**Verdict**: not suitable. Theoretically minimal but practically unusable.

---

## Option 2: BrainF*** (8-Symbol ISA)

Eight operations: `> < + - . , [ ]`

```
>   move data pointer right
<   move data pointer left
+   increment cell at pointer
-   decrement cell at pointer
.   output cell at pointer
,   input to cell at pointer
[   jump past matching ] if cell == 0
]   jump back to matching [ if cell != 0
```

Memory is a tape of 8-bit cells. All arithmetic is increment/decrement.

**Fibonacci in BrainF***:
```
# fib(8) = 21 — known BF programs exist but are ~100 symbols
>++++++++++>+>+[[+++++[>++++++++<-]>.<++++++[>--------<-]+<<<]>.>>
[[-]<[>+<-]>>[<<+>+>-]<[>+<-[>+<-[>+<-[>+<-[>+<-[>+<-[>+<-[>+<-
[>+<-[>[-]>+>+<<<-[>+<-]]]]]]]]]]]+>>>]<<<]
```

### Pros
- Turing complete and well-known.
- Very simple interpreter (~15 lines).
- Models have seen BF programs in training.

### Cons
- Models produce incorrect BF almost always. Writing correct BF for
  anything beyond trivial programs requires careful manual construction.
- 8-bit cells make multi-byte arithmetic (sorting integers > 255) awkward.
- Feature space: cyclomatic complexity is just loop count (`[`); builtin
  reliance is always zero. Less discriminating than a register ISA.
- Programs are unreadable — impossible to inspect or debug.

**Verdict**: not suitable. Novelty metric would be meaningless since models
cannot reliably generate correct programs.

---

## Option 3: Practical Minimal Register ISA (5 instructions)

Registers R0–R7 (32-bit signed integers). Flat memory array. One instruction
per line: `OP dst src` or `OP reg addr`.

```
MOV  dst, src/imm      # dst = src  (or immediate value)
ADD  dst, src/imm      # dst += src
JLZ  reg, label        # if reg < 0: jump to label
LOAD dst, [reg+offset] # dst = mem[reg + offset]
STOR src, [reg+offset] # mem[reg + offset] = src
```

HALT terminates. Input via `IN reg`, output via `OUT reg`.
Subtraction: `ADD dst, -1` or negate then add. Multiplication via loop.
Comparison: subtract, check sign with JLZ.

**Fibonacci iterative in this ISA:**
```
    IN   R0          # n
    MOV  R1, 0       # a = 0
    MOV  R2, 1       # b = 1
loop:
    JLZ  R0, done    # if n < 0: done (use R0-1 trick for == 0)
    ADD  R3, R1      # R3 = a
    ADD  R1, R2      # a = a + b... but need SUB to do n--
```

Note: without SUB, decrementing requires `ADD R0, -1`. Without MUL, 
multiply requires a loop. Doable but tedious.

### Pros
- Genuinely minimal. Turing complete. Simple interpreter.
- Cleaner than SUBLEQ — programs are human-readable.

### Cons
- Without SUB or MUL, models must encode them manually (loops for multiply,
  negate-and-add for subtract). This adds boilerplate that obscures the
  algorithm and inflates cyclomatic complexity for all solutions equally.
- Models will struggle to correctly express sort or two_sum without MUL/SUB.
- The 5-instruction constraint buys theoretical minimalism at the cost of
  practical correctness rate.

**Verdict**: marginally suitable. Correctness rate better than SUBLEQ/BF but
still lower than needed. The forced manual encoding of SUB/MUL flattens the
feature space — all programs have high cyclomatic complexity regardless of
algorithm.

---

## Option 4: Sweet-Spot Register ISA (8–10 instructions)

Registers R0–R7 (32-bit signed). Flat memory. Labels for jumps.

```
MOV  dst, src/imm      # dst = src
ADD  dst, src/imm      # dst += src
SUB  dst, src/imm      # dst -= src
MUL  dst, src/imm      # dst *= src
JZ   reg, label        # jump if reg == 0
JLT  reg, src, label   # jump if reg < src
LOAD dst, [reg+offset] # dst = mem[reg + offset]
STOR src, [reg+offset] # mem[reg + offset] = src
IN   dst               # read next input integer into dst
OUT  src               # emit register value as output
HALT                   # stop
```

No division (avoids divide-by-zero handling). MOD/DIV can be added if needed.

**Fibonacci iterative:**
```
    IN   R0          # n
    MOV  R1, 0       # a = 0
    MOV  R2, 1       # b = 1
loop:
    JZ   R0, done    # if n == 0: done
    MOV  R3, R1      # tmp = a
    ADD  R1, R2      # a = a + b
    MOV  R2, R3      # b = tmp
    SUB  R0, 1       # n--
    JZ   R0, done
    MOV  R3, R1
    ...
```

**Fibonacci matrix exponentiation** would use LOAD/STOR for matrix cells,
MUL and ADD for matrix multiply, JLT/JZ for the halving loop — occupying a
genuinely different cell (O(log n) time, O(1) space, moderate cyclomatic).

### Feature space behaviour

| Algorithm style       | time | space  | cyclomatic | builtins |
|-----------------------|------|--------|------------|----------|
| Iterative loop        | O(n) | O(1)   | simple     | none     |
| Recursive (via stack) | O(n) | O(n)   | moderate   | none     |
| Matrix exp            | O(log n) | O(1) | moderate | none   |
| Table/DP in memory    | O(n) | O(n)   | simple     | none     |

Builtins are always `none` — there is no stdlib. This collapses one axis, but
the other three (time, space, cyclomatic) remain fully discriminating.

### Pros
- Models can write correct programs. The instruction set matches what they
  were trained on (simplified MIPS/RISC-V mental model).
- Algorithms are expressed naturally — iterative fibonacci is ~10 lines,
  binary search is ~15 lines.
- Interpreter is ~50 lines of Python.
- Exact instruction counting — the interpreter increments a counter on every
  opcode, no tracing overhead.
- Fixed 32-bit integers — no big integer issues.
- All arithmetic is constant-time — complexity measurements reflect the
  algorithm, not integer growth.

### Cons
- Builtins axis is always `none` — effectively a 3D feature space.
- More complex to specify and implement than options 1–3.
- Models need the ISA spec in the prompt; without it they'll generate MIPS or
  x86 syntax by default.
- Sorting requires implementing a comparison swap loop — more instructions
  than Python but still tractable.

**Verdict**: best fit for the benchmark. High enough correctness rate to fill
cells, clean measurement environment, and the 3 remaining axes discriminate
well across algorithm families.

---

## Comparison Table

| | SUBLEQ | BrainF*** | Minimal (5) | Sweet-spot (8–10) |
|---|---|---|---|---|
| Instructions | 1 | 8 symbols | 5 | 8–10 |
| Interpreter lines | ~10 | ~15 | ~30 | ~50 |
| Model correctness rate | very low | very low | low | moderate |
| Readable programs | no | no | yes | yes |
| Big integer issues | no | no | no | no |
| Exact instr counting | yes | yes | yes | yes |
| Useful feature axes | 1 (time) | 2 | 3 | 3 |
| Expresses all 6 problems | barely | barely | yes (verbose) | yes (natural) |

---

## Recommendation

**Option 4** (sweet-spot 8–10 instruction ISA). The builtin-reliance axis
collapses to `none` for all programs, reducing the MAP-Elites space to 3D,
but the time/space/cyclomatic axes remain fully discriminating and the
measurement environment is cleaner than Python in every other respect.

The ISA spec goes in the prompt; the interpreter is our infrastructure. Models
already have a strong prior for this style of assembly from MIPS/RISC-V
training data.
