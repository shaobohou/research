# ISA Programmer's Manual

---

## Overview

A simple register machine with 8 general-purpose registers, a flat integer
memory, and an integer I/O tape. Two tiers of available instructions:

- **Core** — 12 opcodes; the minimal Turing-complete set
- **Extended** — adds 4 opcodes and 6 macros for convenience

Programs are plain text, one instruction per line. Execution starts at the
first instruction and proceeds sequentially unless a jump is taken. A core
program terminates by running off the end; an extended program may use `HALT`.

---

## Machine State

### Registers

Eight registers named `R0` through `R7`. Each holds a **32-bit signed
integer**, initialised to 0 at program start. Range: −2,147,483,648 to
2,147,483,647. Arithmetic results that overflow wrap silently (two's
complement).

```
R0  R1  R2  R3  R4  R5  R6  R7
```

No register has a special hardware role. By convention, benchmark programs
use lower-numbered registers for primary variables and higher-numbered
registers for temporaries.

### Memory

A flat array of **32-bit signed integers**, addresses 0–65535, initialised
to 0. Only accessed via `LOAD` and `STOR`. There is no stack pointer or
call stack in hardware; recursive programs must manage their own stack in
memory.

### Program Counter

Points to the next instruction to execute. Advances by one each step unless
a jump instruction redirects it.

### Input / Output

- **Input tape** — a sequence of integers consumed one at a time by `IN`.
  Reading past the end is a runtime error.
- **Output tape** — a sequence of integers produced by `OUT`. The final
  output tape is compared against expected values for correctness checking.

---

## Syntax

### Instructions

```
OPCODE  operand1, operand2, ...
```

Operands are separated by commas. Whitespace around operands is ignored.
Opcodes are case-insensitive (`mov`, `MOV`, and `Mov` are equivalent).

### Labels

A label is an identifier followed by a colon. It may appear on its own line
or on the same line as an instruction:

```
loop:
    ADD R0, 1
    JMP loop
```

```
loop: ADD R0, 1
      JMP loop
```

A label refers to the instruction immediately following it. Multiple labels
may point to the same instruction:

```
start:
entry:
    MOV R0, 0
```

### Comments

Everything after `;` or `#` on a line is ignored:

```
MOV R0, 42   ; load the answer
ADD R0, R1   # add second operand
```

### Operand types

| Notation | Meaning | Example |
|----------|---------|---------|
| `Rn` | register n (0–7) | `R0`, `R7` |
| `imm` | integer literal | `42`, `-1`, `0` |
| `[Rn]` | memory at address in Rn | `[R2]` |
| `[Rn+off]` | memory at Rn + integer offset | `[R2+3]`, `[R1-1]` |
| `label` | jump target | `loop`, `done` |

`dst` must always be a register. `src` may be a register or an immediate.
Memory operands may only appear in `LOAD` and `STOR`.

---

## Core Instruction Set (12 opcodes)

---

### MOV — Move

```
MOV dst, src
```

Copy `src` into register `dst`.

| Operand | Type |
|---------|------|
| dst | register |
| src | register or immediate |

**Examples**

```asm
MOV R0, 42       ; R0 = 42
MOV R1, R0       ; R1 = R0
MOV R2, -1       ; R2 = -1
```

---

### ADD — Add

```
ADD dst, src
```

Add `src` to `dst` and store the result in `dst`. Wraps on overflow.

```asm
MOV R0, 10
ADD R0, 5        ; R0 = 15
ADD R0, R1       ; R0 = R0 + R1
ADD R0, -3       ; R0 = R0 - 3  (subtract via negative immediate)
```

---

### SUB — Subtract

```
SUB dst, src
```

Subtract `src` from `dst` and store the result in `dst`. Wraps on overflow.

```asm
MOV R0, 10
SUB R0, 3        ; R0 = 7
SUB R0, R1       ; R0 = R0 - R1
```

---

### MUL — Multiply

```
MUL dst, src
```

Multiply `dst` by `src` and store the result in `dst`. Wraps on overflow.

```asm
MOV R0, 6
MUL R0, 7        ; R0 = 42
MUL R0, -1       ; R0 = -R0  (negate)
MUL R0, 0        ; R0 = 0
```

---

### DIV — Divide

```
DIV dst, src
```

Divide `dst` by `src` (integer division, truncated toward zero) and store
the result in `dst`. Division by zero is a **runtime error**.

```asm
MOV R0, 7
DIV R0, 2        ; R0 = 3   (truncates, not rounds)
MOV R0, -7
DIV R0, 2        ; R0 = -3  (toward zero, not -4)
```

**Deriving MOD without the extended tier:**

```asm
; R0 = R0 mod R1  (using only core opcodes, result in R0)
MOV  R2, R0      ; R2 = original value
DIV  R2, R1      ; R2 = quotient
MUL  R2, R1      ; R2 = quotient * divisor
SUB  R0, R2      ; R0 = original - quotient*divisor = remainder
```

---

### LOAD — Load from memory

```
LOAD dst, [base+off]
LOAD dst, [base]
```

Read the integer at memory address `(base + off)` into register `dst`.
`off` defaults to 0 when omitted. Reading from an uninitialised address
returns 0.

| Operand | Type |
|---------|------|
| dst | register |
| base | register |
| off | integer literal (may be negative) |

```asm
MOV  R1, 5
LOAD R0, [R1]    ; R0 = mem[5]
LOAD R0, [R1+3]  ; R0 = mem[8]
LOAD R0, [R1-2]  ; R0 = mem[3]
```

**Reading an array:** store the base address in a register and use offsets
or increment the base register to walk through elements.

```asm
MOV  R1, 0       ; index
LOAD R0, [R1]    ; arr[0]
ADD  R1, 1
LOAD R0, [R1]    ; arr[1]
```

---

### STOR — Store to memory

```
STOR src, [base+off]
STOR src, [base]
```

Write `src` to memory address `(base + off)`. `src` may be a register or
an immediate. The memory high-water mark tracks the highest address written;
this is used to measure space complexity.

```asm
MOV  R0, 99
MOV  R1, 10
STOR R0, [R1]    ; mem[10] = 99
STOR 42, [R1+1]  ; mem[11] = 42
STOR R0, [R1-5]  ; mem[5]  = 99
```

---

### JMP — Unconditional jump

```
JMP label
```

Set the program counter to `label`. Execution continues from there.

```asm
    JMP done
    OUT 99       ; never reached
done:
    OUT 0
```

**Infinite loop:**

```asm
loop:
    ADD R0, 1
    JMP loop
```

---

### JZ — Jump if zero

```
JZ reg, label
```

Jump to `label` if `reg == 0`. Otherwise continue to the next instruction.

```asm
MOV R0, 5
JZ  R0, done     ; not taken (R0 != 0)
OUT R0
done:
```

**Deriving equality check (a == b):**

```asm
MOV R2, R0
SUB R2, R1       ; R2 = a - b
JZ  R2, equal    ; jump if a == b
```

**Deriving not-equal (a != b):**

```asm
MOV R2, R0
SUB R2, R1
JZ  R2, skip     ; if equal, skip the jump
JMP not_equal
skip:
```

**Deriving JNZ without the extended tier:**

```asm
; JNZ R0, target  →
JZ  R0, skip
JMP target
skip:
```

---

### JLT — Jump if less than

```
JLT reg, src, label
```

Jump to `label` if `reg < src`. `src` may be a register or an immediate.

```asm
MOV R0, 3
JLT R0, 5, yes   ; taken  (3 < 5)
JLT R0, 3, yes   ; not taken (3 not < 3)
JLT R0, 0, yes   ; not taken (3 not < 0)
```

**Deriving other comparisons from JZ and JLT:**

| Desired | Implementation |
|---------|----------------|
| `a > b` | `JLT b, a, label` (swap operands) |
| `a <= b` | `SUB tmp, a, b; JZ tmp, lbl; JLT tmp, 0, lbl` |
| `a >= b` | `JLT b, a, skip; JMP label; skip:` (a>=b ⟺ not a<b) |

**Deriving JLE without the extended tier:**

```asm
; JLE R0, R1, target  →
MOV R2, R0
SUB R2, R1       ; R2 = a - b
JZ  R2, target   ; jump if a == b
JLT R2, 0, target ; jump if a < b  (i.e. a - b < 0)
```

---

### IN — Read input

```
IN dst
```

Read the next integer from the input tape into register `dst`. If the input
tape is exhausted this is a **runtime error**.

```asm
IN R0    ; read first input
IN R1    ; read second input
```

**Reading an array of n integers:**

```asm
    IN  R0         ; n = array length
    MOV R1, 0      ; index = 0
loop:
    JZ  R0, done   ; exit when count reaches 0... see count-down pattern
    IN  R2
    STOR R2, [R1]
    ADD R1, 1
    SUB R0, 1
    JMP loop
done:
```

---

### OUT — Write output

```
OUT src
```

Append the value of `src` (register or immediate) to the output tape.
Multiple `OUT` instructions append in order.

```asm
OUT R0        ; emit register value
OUT 42        ; emit literal
OUT -1        ; emit -1 (used as sentinel/not-found)
```

---

## Extended Instruction Set (+4 opcodes)

The following opcodes are available when running with `isa='extended'`
(the default). They are derivable from core opcodes but included for
readability.

---

### MOD — Modulo

```
MOD dst, src
```

Set `dst` to `dst mod src`. The sign of the result follows the dividend
(same sign as `dst`). Division by zero is a **runtime error**.

```asm
MOV R0, 10
MOD R0, 3    ; R0 = 1
MOD R0, 4    ; R0 = 2
```

**Primary use:** keeping values bounded, e.g. `MOD R0, 1000000007` for
modular arithmetic in fibonacci/factorial.

---

### JNZ — Jump if not zero

```
JNZ reg, label
```

Jump to `label` if `reg != 0`. Complement of `JZ`.

```asm
MOV R0, 5
JNZ R0, loop   ; taken while R0 != 0
```

---

### JLE — Jump if less than or equal

```
JLE reg, src, label
```

Jump to `label` if `reg <= src`. Complement of `JLT` extended by equality.

```asm
JLE R0, R1, done   ; jump if R0 <= R1
JLE R0, 0, neg     ; jump if R0 <= 0
```

---

### HALT — Halt execution

```
HALT
```

Stop execution immediately. In the core ISA, programs terminate by running
off the end of the instruction list; `HALT` provides an explicit named
termination point useful when multiple exit paths exist.

```asm
    JZ R0, zero_case
    OUT R0
    HALT
zero_case:
    OUT -1
    HALT
```

---

## Macros (+6, extended only)

Macros are expanded at parse time into their base instruction equivalents.
They do not appear in the instruction count.

| Macro | Expands to | Effect |
|-------|-----------|--------|
| `INC reg` | `ADD reg, 1` | reg += 1 |
| `DEC reg` | `SUB reg, 1` | reg -= 1 |
| `CLR reg` | `MOV reg, 0` | reg = 0 |
| `NEG reg` | `MUL reg, -1` | reg = −reg |
| `JGT reg, src, lbl` | `JLT src, reg, lbl` | jump if reg > src |
| `JGE reg, src, lbl` | `JLE src, reg, lbl` | jump if reg >= src |

---

## Runtime Errors

Execution halts and an error is reported for:

| Error | Cause |
|-------|-------|
| Division by zero | `DIV` or `MOD` with src == 0 |
| Input exhausted | `IN` called with empty input tape |
| Step limit exceeded | instruction count reaches `max_steps` (default 10,000,000) |
| Address out of range | `LOAD`/`STOR` to address < 0 or > 65535 |
| Unknown label | jump to a label not defined in the program |

---

## Constraints

Four optional hard constraints enforced by the interpreter:

### register_budget (int)
Only registers R0 through R(budget−1) may be referenced. A program that
names a register outside this range is rejected before execution.

```python
run(prog, inputs, constraints={'register_budget': 4})
# R0-R3 allowed; R4-R7 cause rejection
```

### memory_budget (int)
Memory addresses >= budget may not be read or written. Checked at runtime.

```python
run(prog, inputs, constraints={'memory_budget': 16})
# addresses 0-15 allowed; 16+ cause runtime error
```

### program_size (int)
The instruction count (after macro expansion) must not exceed this value.
Checked before execution.

```python
run(prog, inputs, constraints={'program_size': 32})
```

### whitelist (list of str)
Only the listed opcodes may appear in the program (after macro expansion).
`HALT` is always implicitly allowed.

```python
run(prog, inputs, constraints={'whitelist': ['MOV','ADD','SUB','JZ','JMP','IN','OUT']})
# MUL, DIV, etc. cause rejection
```

---

## Instrumentation

Every execution returns:

| Field | Type | Description |
|-------|------|-------------|
| `outputs` | list[int] | values emitted by OUT |
| `insn_count` | int | total instructions executed (including HALT) |
| `mem_hwm` | int | highest memory address written (0 if memory unused) |
| `error` | str or None | None on success, message on failure |

`insn_count` and `mem_hwm` measured at increasing input sizes are fitted to
complexity classes (O(1) through O(2^n)) to classify time and space
complexity for the MAP-Elites feature space.

---

## Complete Examples

### Fibonacci (iterative, core ISA)

```asm
    IN   R0          ; n
    MOV  R1, 0       ; a = 0
    MOV  R2, 1       ; b = 1
loop:
    JZ   R0, done    ; if n == 0: return a
    MOV  R3, R2      ; tmp = b
    ADD  R2, R1      ; b = a + b
    MOV  R1, R3      ; a = tmp
    SUB  R0, 1       ; n--
    JMP  loop
done:
    OUT  R1
```

Time: O(n) instructions, O(1) memory (mem_hwm = 0).

---

### Factorial (extended ISA, with MOD)

```asm
    IN   R0          ; n
    MOV  R1, 1       ; result = 1
    MOV  R7, 1000000007
loop:
    JZ   R0, done
    MUL  R1, R0
    MOD  R1, R7
    DEC  R0
    JMP  loop
done:
    OUT  R1
    HALT
```

---

### Binary search (extended ISA)

```asm
    IN   R0          ; n (array size)
    CLR  R1          ; read index
read:
    JGE  R1, R0, read_done
    IN   R2
    STOR R2, [R1]
    INC  R1
    JMP  read
read_done:
    IN   R7          ; target
    CLR  R1          ; lo = 0
    MOV  R2, R0
    DEC  R2          ; hi = n-1
search:
    JGT  R1, R2, not_found
    MOV  R3, R1
    ADD  R3, R2
    DIV  R3, 2       ; mid = (lo + hi) / 2
    LOAD R4, [R3]    ; arr[mid]
    MOV  R5, R4
    SUB  R5, R7
    JZ   R5, found   ; arr[mid] == target
    JLT  R4, R7, go_right
    MOV  R2, R3
    DEC  R2          ; hi = mid - 1
    JMP  search
go_right:
    MOV  R1, R3
    INC  R1          ; lo = mid + 1
    JMP  search
found:
    OUT  R3
    HALT
not_found:
    OUT  -1
    HALT
```

Time: O(log n) instructions for the search, O(n) memory for the array.

---

### Insertion sort (extended ISA)

```asm
    IN   R0          ; n
    CLR  R1
read:
    JGE  R1, R0, read_done
    IN   R2
    STOR R2, [R1]
    INC  R1
    JMP  read
read_done:
    MOV  R1, 1       ; i = 1
outer:
    JGE  R1, R0, sort_done
    LOAD R2, [R1]    ; key = arr[i]
    MOV  R3, R1
    DEC  R3          ; j = i - 1
inner:
    JLT  R3, 0, insert
    LOAD R4, [R3]
    JLE  R4, R2, insert
    MOV  R5, R3
    INC  R5
    STOR R4, [R5]    ; arr[j+1] = arr[j]
    DEC  R3
    JMP  inner
insert:
    INC  R3
    STOR R2, [R3]    ; arr[j+1] = key
    INC  R1
    JMP  outer
sort_done:
    CLR  R1
output:
    JGE  R1, R0, halt
    LOAD R2, [R1]
    OUT  R2
    INC  R1
    JMP  output
halt:
    HALT
```

Time: O(n²) instructions (worst case), O(n) memory.
