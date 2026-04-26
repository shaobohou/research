"""
Feature extraction for MAP-Elites coding benchmark.

Empirical: time complexity, space complexity
Static:    cyclomatic complexity, built-in reliance
"""

import ast
import math
import statistics
import subprocess
import sys
import tempfile
import textwrap
import time
import tracemalloc


# ── Complexity classification ─────────────────────────────────────────────────

COMPLEXITY_CLASSES = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n²)", "O(2^n)"]

def _basis(name, n):
    if name == "O(1)":       return 1.0
    if name == "O(log n)":   return math.log2(max(n, 2))
    if name == "O(n)":       return float(n)
    if name == "O(n log n)": return n * math.log2(max(n, 2))
    if name == "O(n²)":      return float(n * n)
    if name == "O(2^n)":     return 2.0 ** min(n, 60)

def _best_fit(sizes, values):
    """Return the complexity class with best R² fit."""
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


# ── Empirical measurement ─────────────────────────────────────────────────────

_MEASURE_TEMPLATE = """
import tracemalloc, time, sys, timeit
sys.setrecursionlimit(100000)

{code}

sizes  = {sizes}
inputs = {inputs}

times  = []
mems   = []
insns  = []
for args in inputs:
    # timing: auto-scale repetitions so measurement > 1ms
    reps = 1
    t = None
    while True:
        try:
            t = timeit.timeit(lambda: solve(*args), number=reps)
        except Exception:
            t = 0.0
            break
        if t > 0.001 or reps >= 10000:
            break
        reps *= 10
    times.append((t or 0.0) / reps)

    # memory: peak allocation
    tracemalloc.start()
    try:
        solve(*args)
    except Exception:
        pass
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    mems.append(peak)

    # instruction count: sys.settrace counting line events (separate from timing run)
    _count = [0]
    def _tracer(frame, event, arg):
        if event == 'line':
            _count[0] += 1
        return _tracer
    sys.settrace(_tracer)
    try:
        solve(*args)
    except Exception:
        pass
    finally:
        sys.settrace(None)
    insns.append(_count[0])

print("TIMES", times)
print("MEMS",  mems)
print("INSNS", insns)
"""

def measure_complexity(code: str, sizes: list, size_input_fn) -> dict:
    """
    Run code on inputs of increasing size, return classified time and space complexity.
    Returns dict with keys: time_complexity, space_complexity, raw_times, raw_mems
    """
    inputs = [size_input_fn(n) for n in sizes]
    script = _MEASURE_TEMPLATE.format(
        code=code, sizes=sizes, inputs=inputs
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script)
        fname = f.name

    try:
        result = subprocess.run(
            [sys.executable, fname],
            capture_output=True, text=True, timeout=30
        )
        lines = result.stdout.strip().splitlines()
        times = mems = insns = None
        for line in lines:
            if line.startswith("TIMES"):
                times = eval(line[6:])
            elif line.startswith("MEMS"):
                mems = eval(line[5:])
            elif line.startswith("INSNS"):
                insns = eval(line[6:])

        if not times or not mems or len(times) != len(sizes):
            return {"time_complexity": "unknown", "space_complexity": "unknown"}

        # Filter out zero times (faster than clock resolution)
        valid = [(s, t, m) for s, t, m in zip(sizes, times, mems) if t > 1e-9]
        if len(valid) < 2:
            return {"time_complexity": "O(1)", "space_complexity": "O(1)", "instruction_count": insns[-1] if insns else 0}

        vs, vt, vm = zip(*valid)
        # Fit instruction counts to complexity classes — more deterministic than timing.
        # Filter insns to match the valid (non-zero-time) subset.
        valid_insns = [insns[i] for i, (s, t, m) in enumerate(zip(sizes, times, mems)) if t > 1e-9] if insns else []
        if len(valid_insns) >= 2:
            time_class = _best_fit(vs, valid_insns)
        else:
            time_class = _best_fit(vs, vt)
        return {
            "time_complexity":  time_class,
            "space_complexity": _best_fit(vs, vm),
            "raw_times": list(vt),
            "raw_mems":  list(vm),
            "raw_insns": insns or [],
        }
    except subprocess.TimeoutExpired:
        return {"time_complexity": "O(2^n)", "space_complexity": "O(2^n)"}
    except Exception as e:
        return {"time_complexity": "unknown", "space_complexity": "unknown"}
    finally:
        import os; os.unlink(fname)


# ── Static analysis ───────────────────────────────────────────────────────────

PYTHON_BUILTINS = {
    "abs", "all", "any", "bin", "bool", "bytes", "callable", "chr", "dict",
    "divmod", "enumerate", "filter", "float", "format", "frozenset", "getattr",
    "hasattr", "hash", "hex", "int", "isinstance", "iter", "len", "list",
    "map", "max", "min", "next", "oct", "ord", "pow", "print", "range",
    "reduce", "repr", "reversed", "round", "set", "setattr", "slice",
    "sorted", "str", "sum", "tuple", "type", "vars", "zip",
}

STDLIB_ATTRS = {
    # common method calls that indicate stdlib/builtin usage
    "sort", "append", "extend", "insert", "pop", "remove", "count",
    "index", "copy", "clear", "update", "get", "items", "keys", "values",
    "join", "split", "strip", "replace", "find", "upper", "lower",
    "lru_cache", "cache", "factorial", "gcd", "log", "sqrt", "ceil", "floor",
}


def cyclomatic_complexity(code: str) -> int:
    """Count decision points: 1 + if/elif/for/while/except/with/assert/comprehension ifs."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0
    count = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                              ast.With, ast.Assert)):
            count += 1
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            count += sum(1 for g in node.generators for _ in g.ifs)
    return count


def builtin_reliance(code: str) -> int:
    """Count calls to Python builtins and common stdlib functions."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in PYTHON_BUILTINS:
                count += 1
            elif isinstance(node.func, ast.Attribute) and node.func.attr in STDLIB_ATTRS:
                count += 1
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            count += 1  # comprehensions count as implicit map/filter
    return count


def bin_cyclomatic(cc: int) -> str:
    if cc <= 3:  return "simple"
    if cc <= 7:  return "moderate"
    return "complex"

def bin_builtins(br: int) -> str:
    if br == 0:  return "none"
    if br <= 3:  return "few"
    return "many"

# ── Full feature vector ───────────────────────────────────────────────────────

def extract_features(code: str, sizes: list, size_input_fn) -> dict:
    """Return all 4 features for a solution."""
    empirical = measure_complexity(code, sizes, size_input_fn)
    cc = cyclomatic_complexity(code)
    br = builtin_reliance(code)
    return {
        "time_complexity":  empirical.get("time_complexity",  "unknown"),
        "space_complexity": empirical.get("space_complexity", "unknown"),
        "cyclomatic":       bin_cyclomatic(cc),
        "builtin_reliance": bin_builtins(br),
        "cyclomatic_raw":   cc,
        "builtin_raw":      br,
    }


def cell_key(features: dict) -> tuple:
    return (
        features["time_complexity"],
        features["space_complexity"],
        features["cyclomatic"],
        features["builtin_reliance"],
    )
