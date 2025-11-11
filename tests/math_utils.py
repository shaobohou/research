"""Utility helpers used to validate repository tooling."""

from __future__ import annotations

from typing import Iterable


def add(values: Iterable[int]) -> int:
    """Return the sum of ``values``.

    The function is intentionally simple so linting, formatting, and type
    checking tools have concrete Python code to analyze.
    """

    total = 0
    for value in values:
        total += value
    return total
