# Notes: wiring tf2jax into the jax `call_tf` test harness

## Goal

Point the existing `jax/experimental/jax2tf/tests/call_tf_test.py` suite at a
`call_tf` implemented with `tf2jax` instead of the upstream
XLA-module-embedding one, and record what breaks.

## Environment

Pinned to a released jax so the checkout and the installed `jaxlib` agree:

| component | version |
| --- | --- |
| jax (source checkout, tag `jax-v0.11.0`, commit `a152174`) | 0.11.0 |
| jaxlib (PyPI) | 0.11.0 |
| tensorflow-cpu | 2.21.0 |
| tf2jax | 0.3.8 (requires jax>=0.7.1) |
| python | 3.12 |

- jax repo HEAD was 0.11.1.dev, PyPI latest was 0.11.0 → checked out the
  `jax-v0.11.0` tag so the test file matches the installed jaxlib.
- `jax.experimental.jax2tf` still exists at this version; no separate jax2tf
  repo needed.
- Ran with `PYTHONPATH=<jax checkout>` so `jax` and the tests come from the
  same source tree, with `jaxlib` from site-packages.
- `JAX_PLATFORMS=cpu`, 4 CPUs, no accelerator.

## How the wiring works

All 97 `call_tf` call sites in `call_tf_test.py` go through the module
attribute `jax2tf.call_tf`, resolved at call time. So a pytest plugin that
rebinds `jax2tf.call_tf` (and `jax2tf.call_tf.call_tf`, for the internal
re-entry from the upstream VJP and from `jax2tf.py`) at `pytest_configure`
redirects the entire suite without touching the test file. That is
`tf2jax_plugin.py`; no diff against the jax checkout is required at all,
which is why there is no `.diff` in this directory.

## Shim design (`call_tf_tf2jax.py`)

Keeps upstream's outer structure — flatten args, canonicalize dtypes,
build `tf.TensorSpec`s, wrap the callable so TF only ever sees a
flat-in/flat-out function, unflatten results — and swaps the middle:

- upstream: `tf.function(..., jit_compile=True)` → get HLO → splice the TF
  program into JAX's lowering as an opaque callee; gradients via
  `tf.GradientTape`.
- shim: `tf2jax.convert(tf.function(...), *specs)` → a pure JAX function;
  gradients via ordinary JAX autodiff over the converted ops.

Chose `tf2jax.convert` over `convert_functional` because the latter raises on
any captured `tf.Variable` (`"Expected function to have no captured
variables"`), and a chunk of the suite captures variables. `convert` surfaces
them as explicit params whose values are read at conversion time — the closest
analogue to upstream capturing them as constants.

Conversions are cached per input signature; JAX calls the wrapped function
once per trace and converting is expensive (traces the `tf.function`, then
walks the GraphDef).

Deliberately *not* papered over — the shim raises `Tf2JaxUnsupported` rather
than quietly doing something different:

- `call_tf_graph=True` — no analogue whatsoever; there is no TF callee left to
  serialize into `stablehlo.custom_call @tf.call_tf_function`.
- `ordered=True` — the converted function is pure JAX, carrying no ordered
  effect.
- `has_side_effects` — can't reject it (defaults to `True` upstream) and can't
  honour it; the guarantee is silently dropped and JAX is free to DCE the call.

One rough edge found while probing: tf2jax's `Variable` is an `np.ndarray`
subclass and leaks into results when a captured variable flows to an output
(`Variable(name='vv:0', ..., numpy=Variable([0., 3., 6.]))` instead of a JAX
array). The shim normalises outputs with `jnp.asarray`.

## Baseline (upstream call_tf, same environment)

`145 passed, 1 failed, 17 skipped` out of 163 collected, in 36s.

The single baseline failure is `CallTfTest::test_multi_platform`, which fails
in tf2xla conversion — it wants more than one platform available and this box
is CPU-only. Environment-related, not a real defect; it is excluded from the
comparison below.

## Results with tf2jax

| configuration | passed | failed | skipped |
| --- | --- | --- | --- |
| upstream `call_tf` (baseline) | 145 | 1 | 17 |
| tf2jax, as shipped | 87 | 59 | 17 |
| tf2jax + version-skew fixes | 116 | 30 | 17 |

See README.md for the analysis; raw logs, per-test JSON and `summary.txt` in
`results/`.

## Working log

1. **First run: 66 failures.** 31 of them were the same
   `RuntimeError: An MLIR function requires a Context`, all in round-trip
   tests. Chased it to tf2jax's `XlaCallModule` parser calling
   `jex.mlir.deserialize_portable_artifact` with no MLIR context.

2. **Chased the skew chain.** Fixing the context revealed the same call now
   returns an `ir.Module` instead of a `str`; fixing that revealed
   `aval_to_ir_type` had gained a `ModuleContext` first argument; fixing that
   revealed `flatten_ir_values` is deprecated and jax's pytest config turns the
   warning into an error. Three patches in `tf2jax_compat.py`, kept opt-in so
   "as shipped" and "skew fixed" stay separately measurable.

   Gotcha: patching `jax._src.interpreters.mlir.aval_to_ir_type` had no effect,
   because tf2jax imports the `jax.interpreters.mlir` re-export shim, which is
   a *different module object* with its own bound names. Had to patch both.

3. **42 failures.** Two buckets turned out to be artifacts of my shim rather
   than tf2jax limits, so I fixed the shim:
   - `ValueError: convert must be used outside all JAX transformations` (5
     tests) came from **`jax2tf.convert`**, not tf2jax. Converting lazily inside
     `wrapped` meant conversion ran under a live JAX trace; in the
     jax→TF→jax→TF tests, tracing the TF function re-enters `jax2tf.convert`,
     which refuses to run while a trace is active. Fixed by doing the
     conversion inside `core.eval_context()` — it only needs the TensorSpecs,
     which are concrete even when the arguments are tracers.
   - 8 `output_shape_dtype` failures were my error *wording* differing from
     upstream's. Aligned the message verbatim so the comparison measures
     behaviour, not strings.

4. **31 failures, 30 of them regressions vs baseline.** All substantive; see
   README.md.

Confirmed passing (these were the ones I expected to break): `test_grad_custom`
both jit modes, `test_custom_grad`, `test_custom_grad_saved_model`,
`test_higher_order_grad` degrees 1-4, `test_pmap`, `test_with_var_read{,_x64}`,
`test_x64_output`, `test_saved_model_variables`, `test_grad_pytree`. tf2jax maps
`tf.custom_gradient` onto `jax.custom_vjp`, so TF-defined gradients survive even
though JAX does the differentiating.

## Dead ends / things that did not work

- `tf2jax.convert_functional` is unusable here: it raises on any captured
  `tf.Variable`, which a large part of the suite has. `tf2jax.convert` is the
  right entry point.
- Parsing `pytest -rf` output for failure reasons: unittest-style failures get
  no message on the `FAILED` line, so the whole bucket-by-cause analysis came
  out empty. Wrote `report_plugin.py` to pull the exception off the report
  object instead.
