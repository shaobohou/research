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
