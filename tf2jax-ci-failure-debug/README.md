# tf2jax CI failure at HEAD — root cause

**Repo:** [google-deepmind/tf2jax](https://github.com/google-deepmind/tf2jax) @ `567b347` (`main` HEAD)
**Failing run:** [actions/runs/31454480871](https://github.com/google-deepmind/tf2jax/actions/runs/31454480871) — `Python 3.12 on ubuntu-latest`, exit code 1 at step 4 (`bash test.sh`)
**Status:** long-standing — the last ~25 nightly scheduled runs all die at the same point (2m53s–3m55s each)

## Summary

CI fails because **`requirements_tests.txt` pins `flax==0.10.6` while `requirements.txt` leaves jax
unpinned (`jax>=0.7.1`)**, so nightly CI now installs **jax 0.11.0** — which removed
`jax.core.get_opaque_trace_state`, a symbol flax 0.10.6 calls on every `nn.Module.init`.

```
flax/core/tracers.py:30: in current_trace
    return jax.core.get_opaque_trace_state(convention="flax")
E   AttributeError: jax.core.get_opaque_trace_state was deprecated in JAX v0.10.0 and
    removed in JAX v0.11.0.  Use jax.extend.core.get_opaque_trace_state.
```

Nothing in tf2jax itself is broken. Every flax-based test dies at model construction:

```
19 failed, 995 passed, 96 skipped in 122.88s
```

All 19 failures raise that one exception. The rest of `test.sh` is clean — flake8 (0 findings),
pylint (exit 24 = refactor/convention bits only, which `pylint-exit -efail -wfail` tolerates),
`setup.py sdist`, and pytest collection all pass.

The `Python 3.13` job is cancelled by `fail-fast`, so it carries no independent signal.

## Failing tests

| Test file | Tests |
|---|---|
| `tf2jax/_src/roundtrip_test.py::Jax2TfTest` | `test_mlp*`, `test_batch_norm*`, `test_conv2d*`, `test_xla_conv*` (16) |
| `tf2jax/_src/tf2jax_test.py::FeaturesTest` | `test_export_saved_model_export_jax_module`, `test_force_bf16_consts_for_leaks__{with,without}_jit` (3) |

Full list in [`failing-tests.txt`](failing-tests.txt); representative traceback in
[`failure-traceback.txt`](failure-traceback.txt).

## Fix

[`tf2jax-requirements-tests-flax-bump.diff`](tf2jax-requirements-tests-flax-bump.diff):

```diff
--- a/requirements_tests.txt
+++ b/requirements_tests.txt
 chex==0.1.89
-flax==0.10.6
+flax==0.12.8
```

flax 0.12.8 declares `jax>=0.10.0` and no longer uses the removed symbol.

### Verified locally

Same container, python 3.12, jax/jaxlib 0.11.0, tensorflow 2.20.0, numpy 2.5.2:

| Config | Result |
|---|---|
| flax 0.10.6, chex 0.1.89 (current pins) | **19 failed**, 995 passed, 96 skipped |
| flax 0.12.8, chex 0.1.92 | 1008 passed, 102 skipped — exit 0 |
| flax 0.12.8, chex 0.1.89 (pin untouched) | 1008 passed, 102 skipped — exit 0 |

**Only the flax pin needs to move.** chex 0.1.89 is not implicated.

The pass-count arithmetic checks out: of the 19 failures, 13 now pass and 6 now reach a
pre-existing `skipTest("native_serialization does not support differentiation without custom
gradient.")` that they previously never got to, because they crashed earlier in `Module.init`.
995 + 13 = 1008, 96 + 6 = 102. No test is being newly masked.

## Also worth fixing (not the cause)

- `.github/workflows/ci.yml` uses `actions/checkout@v2` and `actions/setup-python@v1`; the runner
  flags both as Node 20 deprecations on every run.
- Add `fail-fast: false` to the matrix so the 3.13 job reports independently instead of being
  cancelled by the 3.12 failure.
- Consider an upper bound on `jax` in `requirements.txt`, or pinning it in `requirements_tests.txt`
  alongside tensorflow — the unpinned `jax>=0.7.1` against a pinned flax is exactly what let this
  break silently on a scheduled build.

## Stage 2 of `test.sh`

`test.sh` has a second block that reinstalls `tf-nightly` + jax from GitHub HEAD and reruns
`roundtrip_test`. `set -e` means CI has not reached it in months. Results of running it locally
after the fix: [`stage2-result.md`](stage2-result.md).

## Reproducing

```bash
git clone https://github.com/google-deepmind/tf2jax && cd tf2jax
python3.12 -m venv .venv && source .venv/bin/activate
pip install -U pip setuptools wheel
pip install pytest-xdist -r requirements.txt -r requirements_tests.txt
pip install --no-deps .
mkdir -p _testing && cd _testing
CHECK_CUSTOM_CALLS_TEST=0 pytest -n "$(nproc)" --pyargs tf2jax
```

Working log: [`notes.md`](notes.md).
