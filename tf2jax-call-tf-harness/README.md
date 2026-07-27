# Running jax's `call_tf` test suite against a tf2jax-backed `call_tf`

## Summary

`jax.experimental.jax2tf.call_tf` and `tf2jax` both let JAX code call a
TensorFlow function, by opposite means:

- **`call_tf`** compiles the TF function with XLA and splices the resulting
  program into JAX's computation as an opaque callee. TF stays in the picture
  at runtime; gradients come from `tf.GradientTape`.
- **`tf2jax`** walks the TF `GraphDef` and re-emits each op as JAX ops. The
  result is an ordinary JAX function and nothing TF-specific survives;
  gradients come from JAX autodiff.

This investigation implements `call_tf`'s public signature on top of `tf2jax`
and points jax's own `call_tf_test.py` (163 tests) at it unchanged, to find out
which of `call_tf`'s contracts a graph-level converter can honour.

**Result: 116 of the 146 runnable tests pass on tf2jax.** The 30 that fail
split cleanly into three genuine architectural gaps, an ecosystem bug, and a
tail of error-reporting differences.

Both the released tf2jax (0.3.8) and current main were measured. They land on
the *same* 116/30, but for different reasons — see finding 1.

| configuration | passed | failed | skipped |
| --- | --- | --- | --- |
| upstream `call_tf` (baseline) | 145 | 1 | 17 |
| tf2jax 0.3.8 (PyPI) | 87 | 59 | 17 |
| tf2jax 0.3.8 + skew fixes | 116 | 30 | 17 |
| tf2jax main (`567b347`) | 87 | 59 | 17 |
| tf2jax main + warning downgrade only | 116 | 30 | 17 |
| tf2jax main + all skew fixes | 116 | 30 | 17 |

The single baseline failure (`test_multi_platform`) is a CPU-only-machine
artifact and is excluded from every comparison.

## Key findings

### 1. A single blocker masks everything else — and on main it is only a warning

In both tf2jax versions, **32 of the 59 failures are one issue**, hitting every
jax→TF→jax round-trip. But the issue is not the same one.

**On tf2jax 0.3.8 (PyPI, Aug 2025) it is a hard break.** The `XlaCallModule`
parser (`tf2jax/experimental/ops.py`) does:

```python
mhlo_text = jex.mlir.deserialize_portable_artifact(proto.attr["module"].s)
```

Two things about that call changed in jax since: it now requires an MLIR
`Context` in the surrounding environment, and it returns an `ir.Module` rather
than a `str`. Without a context:

```
RuntimeError: An MLIR function requires a Context but none was provided in the
call or from the surrounding environment.
```

A second break sits behind it: `mlir.aval_to_ir_type(aval)` is now
`aval_to_ir_type(ctx, aval)`.

**On tf2jax main (`567b347`, Jul 2026) both are already fixed.** The
deserialize call is wrapped in `with mlir.make_ir_context():` and handles both
return types, and `aval_to_ir_type` is version-gated behind
`jax.__version_info__ >= (0, 10, 1)`, building the type via
`ir.RankedTensorType.get` instead — the same approach this harness's compat
shim took.

What still blocks those 32 tests on main is only that `mhlo.py` calls
`mlir.flatten_ir_values`, which is **deprecated but functional**. It is fatal
here solely because jax's own pytest config escalates warnings to errors.

The decisive measurement: on main, downgrading *only* that warning and applying
**no API patches at all** gives 116 passed / 30 failed — identical to applying
every patch. So tf2jax main needs no compatibility fixes against jax 0.11.0;
it needs one deprecated call updated before jax removes it.

A separate ecosystem item, present in both tf2jax versions and not tf2jax's
fault: `test_dtypes_{float16,bfloat16}` fail
inside **TensorFlow 2.21's** `tensor_util.MakeNdarray`, which still assigns to
`ndarray.dtype` — deprecated in NumPy 2.5. tf2jax reaches it when constant-folding
half-precision constants; upstream `call_tf` never calls it, so it never trips.

### 2. Three contracts tf2jax structurally cannot honour

These are not bugs, they follow from converting the graph away:

- **`call_tf_graph=True`** (9 tests). This mode serializes the TF callee into a
  `stablehlo.custom_call @tf.call_tf_function`. After tf2jax there is no TF
  callee left to serialize. No workaround exists.
- **Effects** (`has_side_effects`, `ordered`) (1 test). The converted function
  is pure JAX and carries no effect, so JAX may DCE or reorder the call.
  `test_effectful` asserts the jaxpr has effects; it has none.
- **Shape polymorphism** (4 tests). `call_tf` defers to TF's own shape
  inference at lowering time; tf2jax refines a parsed module against concrete
  input shapes, so symbolic dims leak into JAX ops
  (`add got incompatible shapes for broadcasting: (b,), (b + 5,)`).

### 3. tf2jax gets the interesting semantics right

Worth stating explicitly, because these were the ones expected to break:

- **`tf.custom_gradient` is preserved.** `test_grad_custom` and
  `test_custom_grad` pass: tf2jax maps TF custom gradients onto
  `jax.custom_vjp`, so the TF-defined gradient is respected even though the
  differentiation is done by JAX rather than `tf.GradientTape`.
- Higher-order gradients, `grad` through pytrees, variable capture, x64 inputs
  and outputs, `pmap`, and the saved-model round-trips all pass.

### 4. The rest are error-reporting differences, not wrong answers

Six failures are tests asserting that `call_tf` raises a *specific* error, where
tf2jax either raises a different one or succeeds where TF would have refused:

- `test_error_non_compilable_strings` — TF refuses to XLA-compile string ops;
  tf2jax fails earlier with "Support for additional TensorFlow ops are added on
  an as-needed basis", i.e. no `StringToNumber` converter.
- `test_eval_devicearray_arg` — asserts a bfloat16 scalar is *copied*. tf2jax's
  identity is a genuine no-op passthrough, so the buffer is shared and the test's
  `assertRaises(AssertionError)` finds nothing to catch. tf2jax is arguably
  better here.
- `test_saved_model_no_gradients` / `test_without_gradient_saved_model` — a
  saved model with gradients disabled should raise when differentiated; tf2jax
  reports `Differentiation rule for 'mhlo_apply' not implemented` instead of
  jax2tf's message.

## Files

- [`call_tf_tf2jax.py`](call_tf_tf2jax.py) — `call_tf`'s signature implemented
  on `tf2jax.convert`. Keeps upstream's flatten/canonicalize/unflatten
  structure so only the middle differs; raises rather than papering over gaps.
- [`tf2jax_plugin.py`](tf2jax_plugin.py) — pytest plugin that rebinds
  `jax2tf.call_tf` to the shim.
- [`tf2jax_compat.py`](tf2jax_compat.py) — opt-in patches for the tf2jax↔jax
  0.11 API breaks, so "as shipped" and "skew fixed" are measurable separately.
  `TF2JAX_COMPAT=warnings` applies only the DeprecationWarning downgrade and
  none of the API patches, which is what isolates finding 1 on main.
- [`report_plugin.py`](report_plugin.py) — dumps per-test outcomes to JSON
  (`-rf` gives no message for unittest-style failures).
- [`compare_results.py`](compare_results.py) — diffs the runs and buckets
  failures by cause.
- [`results/`](results/) — raw logs, per-test JSON, and `summary.txt`.

## Reproducing

No patch to the jax checkout is needed — all 97 `call_tf` call sites in the
suite resolve `jax2tf.call_tf` as a module attribute at call time, so the
plugin can redirect the whole suite from outside. That is why there is no
`.diff` in this directory.

```bash
git clone --depth 1 https://github.com/jax-ml/jax.git && cd jax
git fetch --depth 1 origin tag jax-v0.11.0 && git checkout jax-v0.11.0

uv venv --python 3.12 venv
VIRTUAL_ENV=$PWD/venv uv pip install 'jax[cpu]==0.11.0' tensorflow-cpu==2.21.0 tf2jax pytest

# for the tf2jax-main runs, replace the released wheel with a git checkout
git clone --depth 1 https://github.com/google-deepmind/tf2jax.git ../tf2jax-src
VIRTUAL_ENV=$PWD/venv uv pip install --no-deps ../tf2jax-src

HARNESS=/path/to/tf2jax-call-tf-harness
export PYTHONPATH=$PWD:$HARNESS JAX_PLATFORMS=cpu

# baseline
python -m pytest jax/experimental/jax2tf/tests/call_tf_test.py -q
# tf2jax as shipped
python -m pytest jax/experimental/jax2tf/tests/call_tf_test.py -q -p tf2jax_plugin
# tf2jax with the version-skew fixes
python -m pytest jax/experimental/jax2tf/tests/call_tf_test.py -q -p tf2jax_plugin -p tf2jax_compat
# tf2jax main, deprecation downgrade only (no API patches)
TF2JAX_COMPAT=warnings python -m pytest jax/experimental/jax2tf/tests/call_tf_test.py -q -p tf2jax_plugin -p tf2jax_compat
```

Pinning to the `jax-v0.11.0` tag matters: the checkout supplies both `jax` and
the test file, while `jaxlib` comes from PyPI, and the two must agree.

## Next steps

- The `deserialize_portable_artifact` / `aval_to_ir_type` breakage is **already
  fixed on tf2jax main** — it only needs a release. Anyone on the 0.3.8 PyPI
  wheel with a recent jax should install from git.
- Replace `mlir.flatten_ir_values` in `tf2jax/experimental/mhlo.py` with
  `mlir.ir_tree_registry.flatten`. It works today but is deprecated, and it is
  the last thing standing between tf2jax main and the round-trip tests.
- The half-precision `MakeNdarray` failure is a TF 2.21 × NumPy 2.5 bug worth
  reporting to TensorFlow separately.
- If `call_tf` semantics are actually wanted from tf2jax, the effects gap is the
  only one that looks cheaply closable (wrap the converted function in a JAX
  effect-carrying primitive). `call_tf_graph` and shape polymorphism are not.
