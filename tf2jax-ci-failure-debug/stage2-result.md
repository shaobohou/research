# Stage 2 of `test.sh` — tf-nightly + jax@HEAD

The tail of `test.sh` swaps the pinned stack for nightlies and reruns the roundtrip tests:

```bash
pip uninstall --yes tensorflow
pip install tf-nightly
pip install git+https://github.com/google/jax.git
pip install -U --pre jaxlib -i https://us-python.pkg.dev/ml-oss-artifacts-published/jax/simple/
CHECK_CUSTOM_CALLS_TEST=0 pytest -n "${N_JOBS}" --pyargs tf2jax._src.roundtrip_test
```

Because of `set -euo pipefail`, CI has not reached this block for months — it dies at the stage-1
pytest first. Ran it locally to confirm the flax bump is actually sufficient to get the whole
script green, rather than just moving the failure downstream.

## Result: passes

Versions resolved on 2026-08-11:

| package | version |
|---|---|
| tf-nightly | 2.22.0.dev20260809 |
| keras-nightly | 3.16.0.dev2026081104 |
| jax | 0.11.1.dev20260811+8d1be7d7d (GitHub HEAD) |
| jaxlib | 0.11.1.dev20260810 (pre-release index) |
| flax | 0.12.8 (the bump) |
| chex | 0.1.89 (unchanged pin) |

All four install commands exited 0, and:

```
109 passed, 96 skipped, 227 warnings in 26.35s
```

pytest exit code 0.

## Note

One deprecation warning shows up 227 times against jax HEAD and is worth cleaning up before it
becomes the next breakage:

```
tf2jax/experimental/mhlo.py:202: DeprecationWarning:
  jax.interpreters.mlir.flatten_ir_values is deprecated.
  Use mlir.ir_tree_registry.flatten instead.
```

It is only a warning today, but `jax.core.get_opaque_trace_state` — the symbol that caused this
whole CI failure — followed exactly the same deprecate-then-remove path.
