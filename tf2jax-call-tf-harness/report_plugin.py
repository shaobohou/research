# Copyright 2026. Apache License 2.0.
"""Pytest plugin that dumps per-test outcomes (and failure reasons) to JSON.

`-rf` only lists node ids for unittest-style failures, with no message, so the
comparison needs the exception text captured directly off the report.

Set the output path with the ``HARNESS_REPORT`` environment variable.
"""

from __future__ import annotations

import json
import os

_RESULTS: dict[str, dict[str, str]] = {}


def pytest_runtest_logreport(report):
  if report.when != "call" and not (report.when == "setup" and
                                    report.outcome == "skipped"):
    return
  entry = _RESULTS.setdefault(report.nodeid, {})
  entry["outcome"] = report.outcome
  if report.outcome == "failed":
    text = str(report.longrepr)
    # The final non-empty line of a traceback is the exception itself.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    entry["reason"] = lines[-1] if lines else ""
    entry["traceback"] = text[-4000:]


def pytest_sessionfinish(session, exitstatus):
  del session, exitstatus
  path = os.environ.get("HARNESS_REPORT")
  if not path:
    return
  with open(path, "w") as f:
    json.dump(_RESULTS, f, indent=1, sort_keys=True)
