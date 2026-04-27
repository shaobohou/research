"""
MAP-Elites coding benchmark for claude-sonnet-4-6.

For each problem:
  - Generate solutions until stopping condition
  - Check correctness via test execution
  - Extract 4 features: time complexity, space complexity, cyclomatic, builtin reliance
  - Fill MAP-Elites archive: score = distinct cells occupied by correct solutions
"""

import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "run"))
import models

from features import extract_features, cell_key
from problems import PROBLEMS

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "results.json")
MAX_ATTEMPTS  = 25
MAX_CONSEC_MISSES = 4   # stop after this many consecutive (fail or filled-cell) attempts


# ── Code extraction ───────────────────────────────────────────────────────────

def _extract_code(text: str) -> str | None:
    m = re.search(r"<code>(.*?)</code>", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # fallback: grab everything inside a python code fence
    m = re.search(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


# ── Correctness check ─────────────────────────────────────────────────────────

_CORRECTNESS_TEMPLATE = """
import sys
sys.setrecursionlimit(100000)

{code}

test_cases = {test_cases}
for args, expected in test_cases:
    result = solve(*args)
    assert result == expected, f"solve({{args}}) = {{result!r}}, expected {{expected!r}}"
print("PASS")
"""

def check_correctness(code: str, test_cases: list) -> tuple[bool, str]:
    script = _CORRECTNESS_TEMPLATE.format(code=code, test_cases=repr(test_cases))
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script)
        fname = f.name
    try:
        r = subprocess.run(
            [sys.executable, fname],
            capture_output=True, text=True, timeout=10
        )
        if r.stdout.strip() == "PASS":
            return True, ""
        return False, (r.stderr or r.stdout).strip()
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)
    finally:
        os.unlink(fname)


# ── Prompt generation ─────────────────────────────────────────────────────────

def _build_prompt(problem: dict, previous_solutions: list[str]) -> str:
    prompt = (
        f"Write a Python function called `solve` that solves the following problem:\n\n"
        f"{problem['description']}\n\n"
        f"Function signature: `{problem['signature']}`\n\n"
        "Requirements:\n"
        "- The function must be named exactly `solve`\n"
        "- Include any necessary imports inside or above the function\n"
        "- Wrap your complete solution in <code></code> XML tags\n"
        "- Provide only the code, no explanation\n"
    )
    if previous_solutions:
        prev_str = "\n\n".join(
            f"<solution id='{i+1}'>\n{s}\n</solution>"
            for i, s in enumerate(previous_solutions)
        )
        prompt += (
            "\nIMPORTANT: You must use a FUNDAMENTALLY DIFFERENT algorithm, approach, "
            "or data structure from all previous solutions. Aim for a different "
            "time/space complexity or implementation strategy.\n\n"
            f"Previous solutions:\n{prev_str}\n"
        )
    return prompt


# ── Main benchmark loop ───────────────────────────────────────────────────────

def run_problem(name: str, problem: dict) -> dict:
    archive    = {}   # cell_key -> solution record
    all_correct = []  # code strings of all correct solutions so far
    attempts   = 0
    consec_misses = 0
    records    = []

    print(f"\n{'='*60}")
    print(f"Problem: {name}")
    print(f"{'='*60}")

    while attempts < MAX_ATTEMPTS and consec_misses < MAX_CONSEC_MISSES:
        attempts += 1
        prompt = _build_prompt(problem, all_correct)

        try:
            response = models.chat_with_model(
                prompt, model="anthropic/claude-sonnet-4",
                max_tokens=1500, temperature=0.7
            )
        except Exception as e:
            print(f"  [{attempts}] API error: {e}")
            consec_misses += 1
            continue

        code = _extract_code(response)
        if not code:
            print(f"  [{attempts}] No code extracted")
            consec_misses += 1
            continue

        passed, err = check_correctness(code, problem["test_cases"])
        if not passed:
            print(f"  [{attempts}] FAIL: {err[:80]}")
            consec_misses += 1
            records.append({"attempt": attempts, "correct": False, "error": err[:120]})
            continue

        # Correct — extract features
        feats = extract_features(code, problem["sizes"], problem["size_input"])
        cell  = cell_key(feats)
        new_cell = cell not in archive

        record = {
            "attempt":                attempts,
            "correct":                True,
            "new_cell":               new_cell,
            "cell":                   list(cell),
            "time_complexity":        feats["time_complexity"],
            "time_complexity_timing": feats["time_complexity_timing"],
            "space_complexity":       feats["space_complexity"],
            "cyclomatic":             feats["cyclomatic"],
            "builtin_reliance":       feats["builtin_reliance"],
            "cyclomatic_raw":         feats["cyclomatic_raw"],
            "builtin_raw":            feats["builtin_raw"],
            "code":                   code,
        }
        records.append(record)
        all_correct.append(code)

        if new_cell:
            archive[cell] = record
            consec_misses = 0
            print(f"  [{attempts}] NEW CELL {cell} — archive size: {len(archive)}")
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


def run_benchmark():
    results = {}
    for name, problem in PROBLEMS.items():
        results[name] = run_problem(name, problem)
        _save(results)

    total = sum(r["score"] for r in results.values())
    avg   = total / len(results)
    print(f"\n{'='*60}")
    print(f"Overall: {total} total cells across {len(results)} problems (avg {avg:.1f})")
    for name, r in results.items():
        print(f"  {r['score']:2d} cells  {name}")
    _save(results)


def _save(results):
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    run_benchmark()
