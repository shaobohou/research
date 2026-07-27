# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Compare the harness runs and bucket the tf2jax-only failures.

Usage:
    uv run compare_results.py results/baseline.json \
        results/tf2jax.json results/tf2jax_compat.json
"""

from __future__ import annotations

import collections
import json
import re
import sys

_LOC_PREFIX = re.compile(r"^.*?\.py:\d+: ")

# Ordered: first match wins.
_BUCKETS = [
    ("call_tf_graph unsupported", ("Tf2JaxUnsupported: call_tf_graph",)),
    ("ordered effects unsupported", ("Tf2JaxUnsupported: ordered",)),
    ("other unsupported call_tf feature", ("Tf2JaxUnsupported",)),
    ("jax API skew (MLIR context)",
     ("An MLIR function requires a Context",)),
    ("jax API skew (aval_to_ir_type)", ("aval_to_ir_type()",)),
    ("jax API skew (deprecated mlir helper)",
     ("flatten_ir_values is deprecated",)),
    ("numpy 2.5 skew via TF MakeNdarray",
     ("Setting the dtype on a NumPy array",
      "create a new array with x.view")),
    ("tf2jax op coverage",
     ("Support for additional TensorFlow ops",
      "NotImplementedError",
      "should be a tf.Tensor")),
    ("error contract not reproduced",
     ("not raised", "does not match")),
    ("shape polymorphism", ("incompatible shapes for broadcasting",
                            "output types match")),
    ("numerical mismatch", ("Mismatched elements", "Not equal to tolerance")),
]


def outcomes(path: str) -> dict[str, dict[str, str]]:
  with open(path) as f:
    return json.load(f)


def reason(entry: dict[str, str]) -> str:
  return _LOC_PREFIX.sub("", entry.get("reason", "")).strip()


# A few failures are unambiguous from the test they come from, but their
# assertion text is too generic to key on.
_BY_NAME = {
    "test_effectful": "effects dropped (has_side_effects/ordered)",
}


def classify(msg: str, name: str = "") -> str:
  short = name.rsplit("::", 1)[-1]
  if short in _BY_NAME:
    return _BY_NAME[short]
  for label, needles in _BUCKETS:
    if any(n in msg for n in needles):
      return label
  return "other"


def tally(data: dict[str, dict[str, str]]) -> str:
  c = collections.Counter(v["outcome"] for v in data.values())
  return (f"{c['passed']} passed, {c['failed']} failed, "
          f"{c['skipped']} skipped")


def main(argv: list[str]) -> int:
  if len(argv) != 4:
    print(__doc__)
    return 2
  base, shipped, patched = (outcomes(p) for p in argv[1:4])

  print("=== totals ===")
  print(f"  upstream call_tf (baseline) : {tally(base)}")
  print(f"  tf2jax, as shipped          : {tally(shipped)}")
  print(f"  tf2jax + version-skew fixes : {tally(patched)}")
  print()

  base_failed = {k for k, v in base.items() if v["outcome"] == "failed"}
  if base_failed:
    print("baseline failures (excluded from every comparison below):")
    for k in sorted(base_failed):
      print(f"  {k.split('::', 1)[-1]}")
    print()

  for label, data in (("tf2jax as shipped", shipped),
                      ("tf2jax + version-skew fixes", patched)):
    regs = {
        k: v for k, v in data.items()
        if v["outcome"] == "failed" and k not in base_failed
    }
    print(f"=== {label}: {len(regs)} failures not present at baseline ===")
    buckets: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    for k, v in regs.items():
      buckets[classify(reason(v), k)].append((k.split("::", 1)[-1], reason(v)))
    for bucket, entries in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
      print(f"\n  [{len(entries)}] {bucket}")
      for name, msg in sorted(entries):
        print(f"      {name}")
        print(f"          {msg[:130]}")
    print()

  fixed = sorted(
      k for k, v in shipped.items()
      if v["outcome"] == "failed" and patched.get(k, {}).get("outcome") == "passed"
  )
  print(f"=== unmasked by the version-skew fixes: {len(fixed)} tests now pass ===")
  for k in fixed:
    print(f"  {k.split('::', 1)[-1]}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main(sys.argv))
