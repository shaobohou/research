# Copyright 2026. Apache License 2.0.
"""Opt-in compatibility shim for tf2jax 0.3.8 against jax 0.11.0.

tf2jax's ``XlaCallModule`` parser (``tf2jax/experimental/ops.py``) does::

    mhlo_text = jex.mlir.deserialize_portable_artifact(proto.attr["module"].s)

Two things about that call changed in jax since tf2jax 0.3.8 (Aug 2025):

1. it now needs an MLIR ``Context`` established in the surrounding
   environment, and raises ``RuntimeError: An MLIR function requires a Context
   but none was provided`` without one;
2. it returns an ``ir.Module`` rather than the MHLO ``str`` that tf2jax's
   downstream code expects.

Any TF graph containing an ``XlaCallModule`` op -- i.e. anything produced by
``jax2tf.convert`` with native serialization -- trips this, which is every
jax->TF->jax round-trip test in the suite.

This patches the entry point rather than the call site so it is a single,
reversible change. Enable with the ``tf2jax_compat`` pytest plugin, so the
harness can measure "tf2jax as shipped" and "tf2jax with the version skew
fixed" separately.
"""

from __future__ import annotations

import os

import jax.extend as jex
from jax._src.interpreters import mlir
from jax._src.lib.mlir import ir
from jax.interpreters import mlir as public_mlir

_ORIG_DESERIALIZE = jex.mlir.deserialize_portable_artifact
_ORIG_AVAL_TO_IR_TYPE = mlir.aval_to_ir_type


def _deserialize_portable_artifact_compat(*args, **kwargs):
  with mlir.make_ir_context():
    result = _ORIG_DESERIALIZE(*args, **kwargs)
    if isinstance(result, str):
      return result
    return mlir.module_to_string(result)


def _aval_to_ir_type_compat(*args):
  """Accept tf2jax's old one-argument ``aval_to_ir_type(aval)`` call.

  jax now threads a ``ModuleContext`` through as the first argument
  (``aval_to_ir_type(ctx, aval)``). tf2jax only ever passes plain
  ``ShapedArray``s here, to refine the input types of a parsed module, so the
  type can be built directly from the ambient ``ir.Context`` without needing a
  ``ModuleContext`` at all. Two-argument calls -- i.e. every call from jax
  itself -- are passed straight through.
  """
  if len(args) == 1:
    aval = args[0]
    return ir.RankedTensorType.get(aval.shape, mlir.dtype_to_ir_type(aval.dtype))
  return _ORIG_AVAL_TO_IR_TYPE(*args)


# `jax.interpreters.mlir` is a re-export shim with its own bound names, and it
# is the one tf2jax imports -- patching only `jax._src.interpreters.mlir` does
# not reach it.
_MLIR_MODULES = (mlir, public_mlir)


def enable():
  """Apply the API patches.

  ``TF2JAX_COMPAT=warnings`` applies none of them, leaving only the
  DeprecationWarning downgrade installed by ``pytest_configure``. tf2jax main
  has already fixed both API breaks, so that mode measures what is left.
  """
  if os.environ.get("TF2JAX_COMPAT") == "warnings":
    return
  jex.mlir.deserialize_portable_artifact = _deserialize_portable_artifact_compat
  for mod in _MLIR_MODULES:
    mod.aval_to_ir_type = _aval_to_ir_type_compat


def disable():
  jex.mlir.deserialize_portable_artifact = _ORIG_DESERIALIZE
  for mod in _MLIR_MODULES:
    mod.aval_to_ir_type = _ORIG_AVAL_TO_IR_TYPE


# tf2jax's MHLO lowering rule calls `mlir.flatten_ir_values`, which still works
# but now emits a DeprecationWarning. jax's own pytest config turns warnings
# into errors, so the call fails the test even though the API is functional.
# Downgrade just this one back to a warning; unlike the two patches above this
# is not a behaviour change, only a reporting one.
_DEPRECATION_FILTERS = (
    "ignore:jax.interpreters.mlir.flatten_ir_values is deprecated"
    ".*:DeprecationWarning",
)


def pytest_configure(config):
  for f in _DEPRECATION_FILTERS:
    config.addinivalue_line("filterwarnings", f)
  enable()


def pytest_unconfigure(config):
  del config
  disable()
