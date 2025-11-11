"""Tests for the placeholder math utilities."""

from .math_utils import add


def test_add_returns_sum() -> None:
    assert add([1, 2, 3]) == 6


def test_add_handles_empty_iterable() -> None:
    assert add([]) == 0
