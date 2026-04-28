"""
Feature extraction for ISA MAP-Elites benchmark.

Feature axes:
  time_complexity  — best-fit complexity class of insn_count vs input size
  space_complexity — best-fit complexity class of mem_hwm vs input size
  program_size_bin — static bin of instruction count after macro expansion
  cyclomatic       — 1 + count of conditional jumps after macro expansion
"""

import math
import statistics
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from interpreter import run, parse

COMPLEXITY_CLASSES = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n²)", "O(2^n)"]

CONDITIONAL_JUMPS = frozenset({"JZ", "JNZ", "JLT", "JLE"})


def _basis(name: str, n: int) -> float:
    if name == "O(1)":
        return 1.0
    if name == "O(log n)":
        return math.log2(max(n, 2))
    if name == "O(n)":
        return float(n)
    if name == "O(n log n)":
        return n * math.log2(max(n, 2))
    if name == "O(n²)":
        return float(n * n)
    if name == "O(2^n)":
        return 2.0 ** min(n, 60)


def _best_fit(sizes: list, values: list) -> str:
    """Return the complexity class whose basis function best fits values vs sizes (by R²)."""
    if len(sizes) < 2:
        return "unknown"
    best, best_r2 = "O(n)", -1e9
    y = [float(v) for v in values]
    y_mean = statistics.mean(y)
    ss_tot = sum((yi - y_mean) ** 2 for yi in y) or 1e-12

    for cls in COMPLEXITY_CLASSES:
        x = [_basis(cls, n) for n in sizes]
        x_mean = statistics.mean(x)
        ss_xy = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
        ss_xx = sum((xi - x_mean) ** 2 for xi in x) or 1e-12
        c = ss_xy / ss_xx
        residuals = [(yi - y_mean - c * (xi - x_mean)) ** 2 for xi, yi in zip(x, y)]
        r2 = 1 - sum(residuals) / ss_tot
        if r2 > best_r2:
            best_r2, best = r2, cls
    return best


def bin_program_size(n: int) -> str:
    if n <= 10:
        return "tiny"
    if n <= 25:
        return "small"
    if n <= 50:
        return "medium"
    return "large"


def cyclomatic_complexity(source: str) -> int:
    """1 + number of conditional jump instructions after macro expansion."""
    try:
        instructions, _ = parse(source)
    except Exception:
        return 0
    return 1 + sum(1 for op, _ in instructions if op in CONDITIONAL_JUMPS)


def bin_cyclomatic(cc: int) -> str:
    if cc <= 3:
        return "simple"
    if cc <= 7:
        return "moderate"
    return "complex"


def extract_features(source: str, sizes: list, encode_fn, max_steps: int = 10_000_000) -> dict:
    """
    Run source on inputs of increasing size and extract MAP-Elites features.

    encode_fn(n) -> list[int]  — input tape for a problem of size n
    """
    insns = []
    hwms = []
    valid_sizes = []
    errors = []

    for n in sizes:
        inputs = encode_fn(n)
        result = run(source, inputs, max_steps=max_steps)
        if result.ok:
            insns.append(result.insn_count)
            hwms.append(result.mem_hwm)
            valid_sizes.append(n)
        else:
            errors.append(f"size {n}: {result.error}")

    if len(valid_sizes) < 2:
        tc = sc = "unknown"
    else:
        all_zero_hwm = all(h == 0 for h in hwms)
        tc = _best_fit(valid_sizes, insns)
        sc = "O(1)" if all_zero_hwm else _best_fit(valid_sizes, hwms)

    try:
        instructions, _ = parse(source)
        prog_size = len(instructions)
    except Exception:
        prog_size = 0

    cc = cyclomatic_complexity(source)
    cc_bin = bin_cyclomatic(cc)

    return {
        "time_complexity": tc,
        "space_complexity": sc,
        "program_size": prog_size,
        "program_size_bin": bin_program_size(prog_size),
        "cyclomatic": cc,
        "cyclomatic_bin": cc_bin,
        "raw_insns": insns,
        "raw_hwms": hwms,
        "valid_sizes": valid_sizes,
        "errors": errors,
    }


def cell_key(features: dict) -> tuple:
    return (
        features["time_complexity"],
        features["space_complexity"],
        features["program_size_bin"],
        features["cyclomatic_bin"],
    )
