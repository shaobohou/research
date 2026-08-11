# Notes — debugging google-deepmind/tf2jax CI failure at HEAD

Date: 2026-08-11
Target: https://github.com/google-deepmind/tf2jax @ `567b347` ("Fix cumsum and cumprod with
exclusive and negative axis.", 2026-07-04) — the current `main` HEAD.

## 1. Getting at the CI state

The session only has GitHub API access to `shaobohou/research`, and `add_repo` refused to attach
`google-deepmind/tf2jax` with credentials ("cross-tier adds are not supported in v1"). So:

- `git clone` of the public repo works (anonymous git read via the proxy) → `/workspace/google-deepmind/tf2jax`.
- `api.github.com` and `github.com` via `curl` are intercepted by the agent proxy → no Actions API,
  no badge, no log download.
- `WebFetch` on the public Actions HTML pages works for *metadata* but not for logs
  ("Sign in to view logs").

What WebFetch gave us:

- Latest ci.yml run: https://github.com/google-deepmind/tf2jax/actions/runs/31454480871
  - **conclusion: failure**
  - job `Python 3.12 on ubuntu-latest` (id 93665353140) → "Process completed with exit code 1",
    annotation anchored at `#step:4:2163` (step 4 = `Run CI tests` → `bash test.sh`)
  - job `Python 3.13 on ubuntu-latest` → cancelled by `fail-fast` (so it carries no independent
    signal)
- The failure is long-standing, not a one-off: the last ~25 scheduled runs all take 2m53s–3m55s,
  i.e. they all die at the same point. The workflow-run filter page reports 182 failing runs.

Since logs were unreachable, the plan became: reproduce `test.sh` locally, faithfully.

## 2. Local reproduction

Environment: Linux container, `python3.12 -m venv`, following `test.sh` step by step.

First attempt used `uv venv`; `pip install --upgrade pip setuptools wheel` then failed with
`Cannot uninstall wheel 0.42.0, RECORD file not found` (Debian-seeded wheel). Irrelevant to the
CI failure — switched to plain `python3.12 -m venv` and it went away.

Resolved dependency versions (what CI gets today, since `requirements.txt` leaves jax unpinned at
`jax>=0.7.1`):

| package | version |
|---|---|
| jax / jaxlib | **0.11.0** |
| tensorflow | 2.20.0 (pinned) |
| numpy | 2.5.2 |
| chex | 0.1.89 (pinned) |
| flax | **0.10.6 (pinned)** |
| setuptools | 84.0.0 |
| pylint | 4.0.7 |
| flake8 | 7.3.0 |

Walked the `test.sh` stages:

- `flake8 ... --select=E9,F63,F7,F82,E225,E251` → 0 findings, exit 0. **not it**
- `pylint --rcfile=.pylintrc` → exit 24 = `8|16` = refactor + convention bits only. `pylint-exit
  -efail -wfail` only fails on fatal/error/warning (1/2/4), so this passes. **not it**
- `python setup.py sdist` → exit 0 (setuptools 84 still allows it). **not it**
- `pytest --collect-only --pyargs tf2jax` → 1110 tests collected, no import errors. **not it**
- `CHECK_CUSTOM_CALLS_TEST=0 pytest -n $(nproc) --pyargs tf2jax`
  → **19 failed, 995 passed, 96 skipped in 122.88s** ← this is the failure

That timing lines up with the observed ~3 min CI runs and with the annotation being deep in the
step-4 log (line 2163).

## 3. Root cause

All 19 failures are the same exception, and it is not raised from tf2jax code:

```
../venv/.../flax/core/tracers.py:30: in current_trace
    return jax.core.get_opaque_trace_state(convention="flax")
E   AttributeError: jax.core.get_opaque_trace_state was deprecated in JAX v0.10.0 and
    removed in JAX v0.11.0.  Use jax.extend.core.get_opaque_trace_state.
```

`requirements_tests.txt` pins `flax==0.10.6`. `requirements.txt` pins nothing above `jax>=0.7.1`,
so the nightly CI now installs jax 0.11.0, in which `jax.core.get_opaque_trace_state` was removed.
flax 0.10.6 calls it on every `nn.Module.init`, so every test that builds a flax model dies at
model construction time.

That is the whole story — 19/19 failures, one cause. The failing tests are the flax-based ones:

- `_src/roundtrip_test.py::Jax2TfTest` — `test_mlp*`, `test_batch_norm*`, `test_conv2d*`,
  `test_xla_conv*` (16)
- `_src/tf2jax_test.py::FeaturesTest` — `test_export_saved_model_export_jax_module`,
  `test_force_bf16_consts_for_leaks__{with,without}_jit` (3)

Secondary observations (not causes, worth a separate cleanup):

- `.github/workflows/ci.yml` still uses `actions/checkout@v2` and `actions/setup-python@v1`,
  both flagged as Node 20 deprecations by the runner.
- `fail-fast` masks the 3.13 job entirely; adding `fail-fast: false` would make future scheduled
  runs more informative.
- The second half of `test.sh` (tf-nightly + jax@HEAD roundtrip tests) has never run recently
  because `set -e` kills the script at the stage-1 pytest.

## 4. Fix and verification

Minimal fix — bump the flax pin (see `tf2jax-requirements-tests-flax-bump.diff`):

```diff
-flax==0.10.6
+flax==0.12.8
```

flax 0.12.8 declares `jax>=0.10.0` and no longer uses the removed symbol.

Verified in the same venv, same jax 0.11.0 / TF 2.20.0:

- flax 0.12.8 + chex 0.1.92 → `1008 passed, 102 skipped` in 134s, exit 0
- flax 0.12.8 + chex **0.1.89** (pin untouched) → `1008 passed, 102 skipped` in 164s, exit 0

So **only the flax pin needs to move**; chex 0.1.89 is fine.

Accounting for the count change 995 passed / 19 failed → 1008 passed / 102 skipped: 13 of the 19
now pass, and 6 now reach their pre-existing `self.skipTest("native_serialization does not support
differentiation without custom gradient.")` line — previously they blew up in `Module.init` before
ever getting there. 995 + 13 = 1008 and 96 + 6 = 102. Nothing is being newly masked.

## 5. Stage 2 of test.sh (tf-nightly + jax@HEAD)

Once stage 1 is fixed, CI will finally reach the second block, which reinstalls `tf-nightly`,
`jax` from GitHub HEAD and pre-release `jaxlib`, then reruns `roundtrip_test`. Ran that locally
too — see `stage2-result.md` for what it found.

---

# Part 2 — full repository scan (2026-08-11)

Follow-on request: scan the whole repo for issues and rank them. Output: `issues.md`.

## What was covered

All of `tf2jax/` (~10.8k lines: `ops.py` 2970, `ops_test.py` 2615, `tf2jax.py` 1532,
`roundtrip_test.py` 1182, plus `numpy_compat.py`, `utils.py`, `config.py`, `xla_utils.py`,
`experimental/{ops,mhlo}.py`, `test_util.py`), `setup.py`, `test.sh`, both workflow files,
`MANIFEST.in`, `.pylintrc`, `README.md`.

## Verification runs (not just reading)

- **pytype**: the CI-disabled command fails on `--use-enum-overlay` (flag removed from current
  pytype). Re-run without it: exactly 1 error, `tf2jax.py:889 No attribute 'tolist' on tuple`,
  traceable to the wrong return annotation on `_OpNode.__call__`.
- **pylint on tests**: the CI-disabled command exits 24 today (refactor/convention only) → would
  pass `pylint-exit -efail -wfail`. Without the `-d W0212,E1123,E1120` workaround it is exit 26 with
  169 `E1120` TF false positives, so the workaround is still load-bearing.
- **XlaCallModule empty `platforms`**: built a real jax2tf graph, cleared the `platforms` attr,
  and converted. Confirmed `ValueError: tuple.index(x): x not in tuple` from
  `experimental/ops.py:236`. Baseline (platforms=[CPU]) converts fine.
- **skip census**: 102 skips over 1110 tests. 66 are the unconditional
  `with_grad and not with_custom_grad` skip at `roundtrip_test.py:70`; 24 are
  `CHECK_CUSTOM_CALLS_TEST=0`, which `test.sh` sets in CI; `sharding_test.py` (2 tests) is TPU-only.
- **packaging**: `python setup.py sdist bdist_wheel` succeeds on setuptools 84 but warns
  `Unknown distribution option: 'tests_require'` and `License classifiers are deprecated`.
- **JAX API probe**: `jax.core.Tracer`, `jax.core.ShapedArray`, `mlir.flatten_ir_values`,
  `jax.extend.sharding.GSPMDSharding`, `jax.lax.optimization_barrier_p` all still resolve on jax
  HEAD; only `jax.core.get_opaque_trace_state` is gone.

## Things checked that turned out NOT to be problems

Worth recording so they are not re-investigated:

- `MaxPool` with `init_value=-jnp.inf` on **int32** input — matches TF exactly (jnp coerces the
  identity). Same for `AvgPool` with `SAME` padding.
- `test_data/**` **is** present in the built wheel, despite setuptools warning
  `Package 'tf2jax.test_data.custom_gradient_cubed' is absent from the packages configuration`.
- `python setup.py --version` still prints only `0.3.9` to stdout under setuptools 84, so the
  version-vs-tag check in `pypi-publish.yml` is not broken by warning noise.
- `_XlaVariadicSort._compute_num_keys` looks like it can leave `num_keys` unbound, but the
  `idx == 0` guard raises before any path reaches the `break`, so it cannot.
- `_EvaluationCache.free_inputs` looks like it could free a parameter still needed by `new_params`,
  but params are counted twice (once as graph input, once as node input), so the refcount never
  reaches zero prematurely.
- `jax.experimental.jax2tf` itself is **not** deprecated in jax 0.11 — only its
  `native_serialization` and `enable_xla` parameters are. tf2jax does not pass either.

## Notable non-findings in ops.py

Read all 130+ op parsers. The conversions themselves are in good shape; the defects found are
peripheral (two f-string bugs, one deprecated logging alias). The `# TODO(b/...)` density is high
(13 in `ops.py`, 8 in `tf2jax.py`) but they are documented limitations, not latent breakage.
