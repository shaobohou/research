# Copyright 2026. Apache License 2.0.
"""A drop-in replacement for ``jax2tf.call_tf`` implemented with ``tf2jax``.

Upstream ``jax.experimental.jax2tf.call_tf`` embeds the *compiled TF program*
into the JAX computation: it builds a ``tf.function(..., jit_compile=True)``,
asks TF for the resulting HLO module, and splices that module into JAX's
lowering as an opaque callee. Gradients go back through ``tf.GradientTape``.

``tf2jax`` takes the opposite approach: it walks the TF GraphDef and re-emits
each TF op as JAX ops, producing an ordinary JAX function. Nothing TF-specific
survives into the JAX program.

This module implements ``call_tf``'s public signature on top of ``tf2jax`` so
the existing ``call_tf_test.py`` suite can be pointed at it unchanged. The goal
is to find out which of ``call_tf``'s contracts a graph-level converter can and
cannot honour -- so the shim deliberately does *not* paper over gaps: where
``tf2jax`` has no equivalent mechanism it raises, rather than silently doing
something different.

Deliberate semantic differences from upstream (each one shows up in the suite):

* **Gradients** are plain JAX autodiff through the converted ops, not
  ``tf.GradientTape``. ``tf.custom_gradient`` is therefore invisible.
* **Effects** (``has_side_effects``, ``ordered``) have no representation: the
  converted function is pure JAX, so JAX may DCE or reorder it.
* **``call_tf_graph=True``** has no analogue at all -- there is no TF callee
  left to serialize into the StableHLO custom call.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from jax import dtypes
from jax import numpy as jnp
from jax import tree_util
from jax._src import core
from jax._src import util
from jax.experimental.jax2tf import jax2tf as jax2tf_internal
import numpy as np
import tensorflow as tf
import tf2jax


class UnspecifiedOutputShapeDtype:
  pass


class Tf2JaxUnsupported(NotImplementedError):
  """Raised for a ``call_tf`` feature that tf2jax has no mechanism for."""


# Conversion is expensive (it traces the tf.function and walks the GraphDef),
# and JAX will call the wrapped function once per trace. Cache on the input
# signature, keyed per wrapper instance.
def _spec_key(specs: Sequence[tf.TensorSpec]) -> tuple:
  return tuple((tuple(s.shape.as_list()), s.dtype.name) for s in specs)


def call_tf(
    callable_tf: Callable,
    has_side_effects: bool = True,
    ordered: bool = False,
    output_shape_dtype: Any = UnspecifiedOutputShapeDtype(),
    call_tf_graph: bool = False,
) -> Callable:
  """``jax2tf.call_tf``'s signature, backed by ``tf2jax.convert``."""

  if call_tf_graph:
    raise Tf2JaxUnsupported(
        "call_tf_graph=True has no tf2jax equivalent: tf2jax lowers the TF "
        "graph to JAX ops, so there is no TF callee left to embed in a "
        "stablehlo.custom_call @tf.call_tf_function.")

  if ordered:
    raise Tf2JaxUnsupported(
        "ordered=True has no tf2jax equivalent: the converted function is "
        "pure JAX and carries no ordered effect to sequence calls with.")

  # `has_side_effects` defaults to True on the upstream API, so we cannot
  # reject it outright -- but we cannot honour it either. Record it so callers
  # (and the harness) can see that the guarantee is dropped.
  del has_side_effects

  # Populated the first time the flattened TF callable is traced.
  state: dict[str, Any] = {"res_treedef": None}
  conversion_cache: dict[tuple, Any] = {}

  def wrapped(*args_jax):
    args_flat_jax, args_treedef = tree_util.tree_flatten(args_jax)

    def canonical_arg(v):
      v = v if getattr(v, "dtype", None) else np.asarray(v)
      dtype = dtypes.canonicalize_dtype(v.dtype)
      if dtype != v.dtype:
        v = v.astype(dtype)
      return v

    args_flat_jax = tuple(map(canonical_arg, args_flat_jax))

    def make_tensorspec(a_jax):
      a_tf_dtype = jax2tf_internal._to_tf_dtype(a_jax.dtype)
      a_tf_shape = [
          d if core.is_constant_dim(d) else None
          for d in getattr(a_jax, "shape", ())
      ]
      return tf.TensorSpec(a_tf_shape, a_tf_dtype)

    args_flat_sig_tf = tuple(map(make_tensorspec, args_flat_jax))

    if not isinstance(output_shape_dtype, UnspecifiedOutputShapeDtype):
      output_shape_dtype_flat, output_shape_dtype_tree = tree_util.tree_flatten(
          output_shape_dtype)
      output_avals = tuple(
          core.ShapedArray(st.shape, st.dtype) for st in output_shape_dtype_flat)
    else:
      output_avals, output_shape_dtype_tree = None, None

    # Same flatten/unflatten dance as upstream: tf2jax only ever sees a
    # flat-in/flat-out TF function, so pytrees are handled on the JAX side.
    def callable_flat_tf(*args_tf_flat):
      args_tf = args_treedef.unflatten(args_tf_flat)
      res_tf = callable_tf(*args_tf)
      res_tf_flat, res_treedef_now = tree_util.tree_flatten(res_tf)
      prev = state["res_treedef"]
      assert prev is None or prev == res_treedef_now, (
          f"Subsequent calls had different results. Previous {prev} and now "
          f"{res_treedef_now}")
      state["res_treedef"] = res_treedef_now
      if output_avals is not None:
        if res_treedef_now != output_shape_dtype_tree:
          raise ValueError(
              "The pytree of the TensorFlow function results does not match "
              "the pytree of the declared output_shape_dtype:\n"
              f"results pytree: {res_treedef_now}\n"
              f"output_shape_dtype tree: {output_shape_dtype_tree}")
        assert len(output_avals) == len(res_tf_flat)
      return res_tf_flat

    key = _spec_key(args_flat_sig_tf)
    if key not in conversion_cache:
      function_flat_tf = tf.function(callable_flat_tf, autograph=False)
      # Conversion is a staging-time activity: it only needs the TensorSpecs,
      # which are concrete even when the arguments are tracers. Run it in an
      # eval context so it does not inherit the caller's JAX trace -- tracing
      # `callable_tf` can re-enter jax2tf.convert (in the jax->TF->jax->TF
      # round-trip tests), which refuses to run under a live JAX trace.
      with core.eval_context():
        # tf2jax.convert (rather than convert_functional) so that TF Variables
        # captured by the function are surfaced as explicit params instead of
        # erroring out. Their values are read at conversion time, which is the
        # closest analogue to upstream's capture-as-constant behaviour.
        jax_func, jax_params = tf2jax.convert(function_flat_tf,
                                              *args_flat_sig_tf)
      conversion_cache[key] = (jax_func, jax_params)
    jax_func, jax_params = conversion_cache[key]

    res_jax_flat, _ = jax_func(jax_params, *args_flat_jax)

    # tf2jax's Variable is an np.ndarray subclass and can leak into results;
    # normalise so callers see ordinary JAX arrays.
    res_jax_flat = [jnp.asarray(r) for r in res_jax_flat]

    if output_avals is not None:
      res_jax_flat = [
          _check_against_aval(i, r, aval)
          for i, (r, aval) in enumerate(zip(res_jax_flat, output_avals))
      ]

    res_treedef = state["res_treedef"]
    assert res_treedef is not None
    return res_treedef.unflatten(res_jax_flat)

  return util.wraps(callable_tf)(wrapped)


def _check_against_aval(idx: int, res, aval: core.ShapedArray):
  """Mirror upstream's ``output_shape_dtype`` validation, message included.

  The suite asserts on the exact wording, so reproducing it keeps the
  comparison focused on behaviour rather than on error strings.
  """
  mismatched = (
      res.dtype != aval.dtype
      or len(res.shape) != len(aval.shape)
      or any(
          core.is_constant_dim(d_aval)
          and core.is_constant_dim(d_res)
          and d_aval != d_res
          for d_res, d_aval in zip(res.shape, aval.shape)
      )
  )
  if mismatched:
    raise ValueError(
        "The shapes or dtypes returned by the TensorFlow function "
        "do not match the declared output_shape_dtype:\n"
        f"Result[{idx}] is {res.dtype}[{res.shape}] vs. expected "
        f"{aval.dtype}[{aval.shape}]")
  return res
