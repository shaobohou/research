# Copyright 2026. Apache License 2.0.
"""Pytest plugin that points ``jax2tf.call_tf`` at the tf2jax-backed shim.

Usage (from a jax checkout, with this directory on PYTHONPATH):

    pytest jax/experimental/jax2tf/tests/call_tf_test.py -p tf2jax_plugin

The suite reaches ``call_tf`` exclusively as the module attribute
``jax2tf.call_tf`` (all 97 call sites in ``call_tf_test.py``), and it resolves
that attribute at call time, so rebinding it here -- before collection -- is
enough to redirect the whole suite.
"""

from __future__ import annotations

import call_tf_tf2jax
from jax.experimental import jax2tf
from jax.experimental.jax2tf import call_tf as call_tf_module

_ORIGINAL = jax2tf.call_tf


def pytest_configure(config):
  del config
  jax2tf.call_tf = call_tf_tf2jax.call_tf
  # Upstream's own VJP re-enters `call_tf` via the module-level name, and
  # jax2tf.py imports it for the TF round-trip. Rebind both so nothing falls
  # back to the original implementation behind our back.
  call_tf_module.call_tf = call_tf_tf2jax.call_tf


def pytest_unconfigure(config):
  del config
  jax2tf.call_tf = _ORIGINAL
  call_tf_module.call_tf = _ORIGINAL
