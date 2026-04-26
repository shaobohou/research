"""
MAP-Elites ISA coding benchmark.

For each problem:
  - Prompt an LLM to write ISA assembly
  - Check correctness by running the interpreter
  - Extract features: time_complexity, space_complexity, program_size_bin
  - Fill MAP-Elites archive: score = distinct (time, space, size) cells occupied

Feature axes (cell dimensions):
  time_complexity   6 classes  O(1) … O(2^n)
  space_complexity  6 classes  O(1) … O(2^n)
  program_size_bin  4 bins     tiny / small / medium / large
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "run"))
import models

from interpreter import run as isa_run
from features import extract_features, cell_key
from problems import PROBLEMS

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "results.json")
MAX_ATTEMPTS       = 25
MAX_CONSEC_MISSES  = 4

# ── ISA cheatsheet included in every prompt ───────────────────────────────────

_ISA_CHEATSHEET = """
## ISA Reference (extended tier)

Machine: 8 registers R0-R7 (32-bit signed, init 0), flat memory mem[0..65535] (32-bit signed, init 0).
Program reads integers from an input tape (IN) and writes integers to an output tape (OUT).
Execution ends when the program falls off the last instruction, or executes HALT.
All arithmetic wraps at 32-bit signed boundaries.

### Syntax
- Labels:   `LOOP:` (on its own line or prefixed to an instruction)
- Comments: everything after `;` or `#` is ignored
- Memory:   `[R2]`, `[R3+4]`, `[R1-8]`
- Literals: any signed integer, e.g. `0`, `-1`, `1000000007`

### Opcodes
| Opcode              | Effect                                              |
|---------------------|-----------------------------------------------------|
| MOV  Rd, Rs/imm     | Rd = Rs (or immediate)                              |
| ADD  Rd, Rs/imm     | Rd += Rs                                            |
| SUB  Rd, Rs/imm     | Rd -= Rs                                            |
| MUL  Rd, Rs/imm     | Rd *= Rs                                            |
| DIV  Rd, Rs/imm     | Rd = trunc(Rd / Rs)  (truncated toward zero)        |
| MOD  Rd, Rs/imm     | Rd = Rd % Rs         (Python-style, sign of divisor)|
| LOAD Rd, [Rb+off]   | Rd = mem[Rb + off]                                  |
| STOR Rs, [Rb+off]   | mem[Rb + off] = Rs                                  |
| IN   Rd             | Rd = next value from input tape                     |
| OUT  Rs/imm         | append Rs to output tape                            |
| JMP  label          | unconditional jump                                  |
| JZ   Rs, label      | jump if Rs == 0                                     |
| JNZ  Rs, label      | jump if Rs != 0                                     |
| JLT  Ra, Rb, label  | jump if Ra < Rb                                     |
| JLE  Ra, Rb, label  | jump if Ra <= Rb                                    |
| HALT                | stop execution                                      |

### Macros (expand at parse time)
INC Rd        →  ADD Rd, 1
DEC Rd        →  SUB Rd, 1
CLR Rd        →  MOV Rd, 0
NEG Rd        →  MUL Rd, -1
JGT Ra,Rb,lbl →  JLT Rb, Ra, lbl
JGE Ra,Rb,lbl →  JLE Rb, Ra, lbl
""".strip()


# ── Assembly extraction ───────────────────────────────────────────────────────

def _extract_asm(text: str) -> str | None:
    """Pull assembly from <code>…</code> or a fenced code block."""
    m = re.search(r"<code>(.*?)</code>", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"```(?:asm|assembly|nasm)?\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


# ── Correctness check ─────────────────────────────────────────────────────────

def check_correctness(source: str, test_cases: list) -> tuple[bool, str]:
    """
    Run source on each test case's input tape and compare outputs.
    test_cases: list of (input_tape: list[int], expected_outputs: list[int])
    """
    for i, (inputs, expected) in enumerate(test_cases):
        result = isa_run(source, inputs, max_steps=5_000_000)
        if not result.ok:
            return False, f"case {i}: runtime error — {result.error}"
        if result.outputs != expected:
            return False, (
                f"case {i}: inputs={inputs} → outputs={result.outputs}, "
                f"expected={expected}"
            )
    return True, ""


# ── Prompt generation ─────────────────────────────────────────────────────────

def _build_prompt(problem: dict, previous_solutions: list[str]) -> str:
    prompt = (
        f"Write an assembly program for the following custom ISA that solves:\n\n"
        f"**Problem:** {problem['description']}\n\n"
        f"**I/O protocol:** {problem['io_description']}\n\n"
        f"{_ISA_CHEATSHEET}\n\n"
        "Requirements:\n"
        "- Wrap your complete assembly in <code></code> XML tags\n"
        "- The program must read all required inputs via IN and write the answer via OUT\n"
        "- Provide only the assembly, no explanation\n"
    )
    if previous_solutions:
        prev_str = "\n\n".join(
            f"<solution id='{i+1}'>\n{s}\n</solution>"
            for i, s in enumerate(previous_solutions)
        )
        prompt += (
            "\nIMPORTANT: Use a FUNDAMENTALLY DIFFERENT algorithm or structure "
            "from all previous solutions — aim for a different time/space trade-off "
            "(e.g. iterative vs. recursive-style unrolling, different loop structure, "
            "different memory layout, fewer or more registers).\n\n"
            f"Previous solutions:\n{prev_str}\n"
        )
    return prompt


# ── Main benchmark loop ───────────────────────────────────────────────────────

def run_problem(name: str, problem: dict) -> dict:
    archive       = {}
    all_correct   = []
    attempts      = 0
    consec_misses = 0
    records       = []

    print(f"\n{'='*60}")
    print(f"Problem: {name}")
    print(f"{'='*60}")

    while attempts < MAX_ATTEMPTS and consec_misses < MAX_CONSEC_MISSES:
        attempts += 1
        prompt = _build_prompt(problem, all_correct)

        try:
            response = models.chat_with_model(
                prompt, model="anthropic/claude-sonnet-4",
                max_tokens=2000, temperature=0.7
            )
        except Exception as e:
            print(f"  [{attempts}] API error: {e}")
            consec_misses += 1
            continue

        source = _extract_asm(response)
        if not source:
            print(f"  [{attempts}] No assembly extracted")
            consec_misses += 1
            continue

        passed, err = check_correctness(source, problem["test_cases"])
        if not passed:
            print(f"  [{attempts}] FAIL: {err[:100]}")
            consec_misses += 1
            records.append({"attempt": attempts, "correct": False, "error": err[:160]})
            continue

        feats    = extract_features(source, problem["sizes"], problem["encode_fn"])
        cell     = cell_key(feats)
        new_cell = cell not in archive

        record = {
            "attempt":          attempts,
            "correct":          True,
            "new_cell":         new_cell,
            "cell":             list(cell),
            "time_complexity":  feats["time_complexity"],
            "space_complexity": feats["space_complexity"],
            "program_size":     feats["program_size"],
            "program_size_bin": feats["program_size_bin"],
            "raw_insns":        feats["raw_insns"],
            "raw_hwms":         feats["raw_hwms"],
            "source":           source,
        }
        records.append(record)
        all_correct.append(source)

        if new_cell:
            archive[cell] = record
            consec_misses = 0
            print(f"  [{attempts}] NEW CELL {cell} — archive: {len(archive)}")
        else:
            consec_misses += 1
            print(f"  [{attempts}] correct but cell {cell} already filled")

    print(f"  Done — {len(archive)} distinct cells from {attempts} attempts")
    return {
        "score":    len(archive),
        "attempts": attempts,
        "cells":    {str(k): v for k, v in archive.items()},
        "records":  records,
    }


def run_benchmark(problems: list[str] | None = None):
    if problems is None:
        problems = list(PROBLEMS.keys())

    results = {}
    for name in problems:
        results[name] = run_problem(name, PROBLEMS[name])
        _save(results)

    total = sum(r["score"] for r in results.values())
    avg   = total / len(results) if results else 0
    print(f"\n{'='*60}")
    print(f"Overall: {total} total cells across {len(results)} problems (avg {avg:.1f})")
    for name, r in results.items():
        print(f"  {r['score']:2d} cells  {name}")
    _save(results)


def _save(results: dict):
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("problems", nargs="*",
                        help="problem names to run (default: all)")
    args = parser.parse_args()
    run_benchmark(args.problems or None)
