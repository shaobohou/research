# tf2jax — prioritized issue scan

**Repo:** [google-deepmind/tf2jax](https://github.com/google-deepmind/tf2jax) @ `567b347` (`main` HEAD, 2026-07-04)
**Scanned:** 2026-08-11 — all ~10.8k lines of `tf2jax/`, plus `setup.py`, `test.sh`, both workflows, `README.md`
**Method:** static read + runtime verification in a python 3.12 venv (jax 0.11.0 / TF 2.20.0), plus a full pytype run, a pylint run on the test files, a build of the sdist/wheel, and a targeted repro for the XlaCallModule bug.

Everything marked **verified** below was reproduced or measured in this session; everything marked
**observed** is a static reading I did not execute.

---

## P0 — CI is red

### 1. `flax==0.10.6` pin is incompatible with jax 0.11 — 19 test failures *(verified)*

`requirements_tests.txt` pins `flax==0.10.6`; `requirements.txt` leaves jax at `jax>=0.7.1`, so nightly
CI installs jax 0.11.0, which removed `jax.core.get_opaque_trace_state`. flax 0.10.6 calls it on
every `nn.Module.init`.

```
flax/core/tracers.py:30: in current_trace
    return jax.core.get_opaque_trace_state(convention="flax")
E   AttributeError: jax.core.get_opaque_trace_state was deprecated in JAX v0.10.0 and
    removed in JAX v0.11.0.
```

All 19 failures are this one exception. Fix: bump the pin to `flax==0.12.8`
(`tf2jax-requirements-tests-flax-bump.diff`). Verified green with chex left at 0.1.89, and the
tf-nightly + jax@HEAD stage of `test.sh` passes afterwards too. Full detail in [`README.md`](README.md).

---

## P1 — structural / real defects

### 2. Unpinned `jax` against pinned `flax`/`tensorflow` is the root cause, and will recur *(verified)*

`requirements.txt` says `jax>=0.7.1` / `jaxlib>=0.7.1` with no upper bound, while
`requirements_tests.txt` pins `tensorflow==2.20.0` and `flax==0.10.6` exactly. A nightly scheduled
build therefore silently drifts onto whatever JAX shipped that day against frozen partners. Issue #1
is the first casualty; there will be another.

Suggested: give `jax`/`jaxlib` an upper bound in `requirements.txt`, or pin them in
`requirements_tests.txt` next to tensorflow and let a separate scheduled job track HEAD (which
`test.sh` already does in its second stage).

### 3. `XlaCallModule` with an empty `platforms` attr crashes with an opaque error *(verified)*

`tf2jax/experimental/ops.py:236`:

```python
if target_platforms and jax_backend not in target_platforms:
    ...
    return None
else:
    return target_platforms.index(jax_backend)   # () .index(...) -> ValueError
```

When `platforms` is empty the guard is falsy, so control falls to `.index()` on an empty tuple.
`_xla_call_module` accepts `version >= 2`, and `platforms` predates the versions that always set it.

Reproduced by clearing the attr on a real jax2tf-produced graph:

```
platforms = [b'CPU'] -> OK -> [0. 0.39733866 0.77883667]
platforms = []       -> ValueError: tuple.index(x): x not in tuple
```

Fix: `return target_platforms.index(jax_backend) if target_platforms else None`.

### 4. Nightly failures reach nobody *(observed)*

`ci.yml` has `schedule: cron '30 2 * * *'` but no notification step, and the workflow-run filter
reports 182 failed runs. The break in #1 ran unattended for months. Worth adding a failure
notification (issue-on-failure action, or a required check surfaced elsewhere).

### 5. `fail-fast` hides the Python 3.13 job *(verified)*

The 3.13 job in the failing run was cancelled — "The strategy configuration was canceled because
'build-and-test._3_12_ubuntu-latest' failed" — so a 3.13-only regression is invisible until 3.12 is
green. Add `fail-fast: false` to the matrix.

### 6. Stale action versions *(verified)*

`actions/checkout@v2` and `actions/setup-python@v1`. The runner emits a Node 20 deprecation
annotation on every job. `setup-python@v1` is six majors behind and predates version caching.
(`pypi-publish.yml` is on `@v4`, also Node 20.)

---

## P2 — quality gates that are disabled but pass today

### 7. pytype has been off since "TF 2.14"; it now reports exactly one error *(verified)*

`test.sh:52-55` disables pytype pending a TF 2.14 release. TF is at 2.20. Two things block a
straight re-enable:

- the pinned command passes `--use-enum-overlay`, which current pytype rejects
  (`pytype: error: unrecognized arguments: --use-enum-overlay`);
- with that flag dropped, `pytype $(find tf2jax/_src/ -name "*py") -k` reports **1** error:

```
tf2jax/_src/tf2jax.py:889:38: error: in _infer_relu_from_jax2tf:
    No attribute 'tolist' on tuple [attribute-error]
```

That one is a genuine annotation inaccuracy: `_OpNode.__call__` is declared to return
`Tuple[Tuple[jnp.ndarray, ...], Mapping[...]]`, but ops actually return a bare array, a tuple, or
`_EMPTY_RETURN_VALUE`. Fixing the annotation (or suppressing at the call site) unblocks the gate.

### 8. pylint on `*_test.py` is disabled but would pass *(verified)*

`test.sh:41-45` disables it pending [pylint-dev/pylint#9185]. Running the documented command today:

```
python -m pylint --rcfile=.pylintrc $(find tf2jax -name '*_test.py') -d W0212,E1123,E1120
  -> exit 24  (refactor + convention bits only)
```

`pylint-exit -efail -wfail` only fails on fatal/error/warning, so this passes as-is and can be
re-enabled now. The `-d` list is still needed: without it the run is exit 26 with 169
`E1120 no-value-for-parameter` false positives from TensorFlow.

[pylint-dev/pylint#9185]: https://github.com/pylint-dev/pylint/issues/9185

---

## P3 — test-coverage holes

Measured on the full suite (1110 collected, 102 skipped):

| skips | reason |
|---:|---|
| 66 | `native_serialization does not support differentiation without custom gradient.` |
| 24 | `Disable tests with custom calls whose targets have no compatibility guarantees.` |
| 6 | `Not a test.` |
| 4 | `No differentiation rule for reduce_window with jax.lax.cumprod.` |
| 1 | `Only run sharding tests on TPU.` |
| 1 | `Gradient is disallowed for jax.lax.scatter_mul if unique_indices=False` |

### 9. 66 roundtrip tests can never run *(verified)*

`roundtrip_test.py:70-74` — `_test_convert` skips unconditionally when
`with_grad and not with_custom_grad`. Every parameterization in that quadrant of the matrix is dead;
`chex.params_product` still generates and names them, so the suite advertises coverage it does not
have. Either drop that quadrant from the parameterization or make the skip conditional on something
that can change.

### 10. Custom-call tests never run in CI *(verified)*

`test.sh` sets `CHECK_CUSTOM_CALLS_TEST=0` on **both** pytest invocations, which disables 24 tests.
They exist only for local runs.

### 11. `sharding_test.py` has zero CI coverage *(verified)*

156 lines, 2 collected tests, both gated on `Only run sharding tests on TPU.` The matrix is
`ubuntu-latest` CPU only.

Net effect: of `roundtrip_test`'s 205 tests, ~95 are skipped in CI (~46%).

### 12. Ops with explicit "add test" TODOs *(observed)*

`ResourceGather` + `dtype`/`validate_indices` (`ops.py:1041`, b/249826984), `VarHandleOp`
(`ops.py:2356`, b271811043), `BatchMatMulV2` with complex values (`ops.py:1215`, b/266553251).

---

## P4 — code defects, low severity

### 13. Two error messages are missing their `f` prefix *(verified)*

```python
# ops.py:2349
raise ValueError("Unpack expects dimension of {num} for axis={axis}, "
                 "found {x.shape[axis]}, shape={x.shape}")
# ops.py:2851
raise ValueError("Reducer not supported as `update_computation`, found {jaxpr}")
```

Both print literal braces instead of values.

### 14. `logging.warn` is deprecated *(verified)*

`ops.py:1079` — `The 'warn' function is deprecated, use 'warning' instead`. Every other call site in
the file already uses `logging.warning`.

### 15. `mlir.flatten_ir_values` is deprecated on jax HEAD *(verified)*

`experimental/mhlo.py:202` raises 227 `DeprecationWarning`s per test run:
`jax.interpreters.mlir.flatten_ir_values is deprecated. Use mlir.ir_tree_registry.flatten instead.`
This is the same deprecate-then-remove path that produced issue #1; worth clearing before it becomes
a breakage.

### 16. Dead compatibility branches *(observed)*

- `numpy_compat.py:71-89` — `if jax.__version_info__ >= (0, 4, 30)` with a fallback for older JAX,
  while `requirements.txt` demands `jax>=0.7.1`.
- `utils.py:53-62` — `if sys.version_info >= (3, 10)` with a manual `safe_zip` fallback, while
  `setup.py` sets `python_requires='>=3.12'`.

### 17. `test_util.parse_version` is unused *(verified)*

Defined at `test_util.py:26`, never called; `linalg_ops_test.py:34` defines its own `_parse_version`.

### 18. `setup.py` warnings *(verified)*

Building the sdist/wheel emits:

- `UserWarning: Unknown distribution option: 'tests_require'` — setuptools removed it; the
  `tests_require=` argument does nothing.
- `SetuptoolsDeprecationWarning: License classifiers are deprecated` — move to SPDX
  `license = "Apache-2.0"`.
- `packages=find_packages(exclude=['*_test.py'])` — `exclude` matches *package* names, not modules,
  so it excludes nothing. Test modules do ship in the wheel, which `test.sh`'s `pytest --pyargs`
  actually depends on; the pattern is just misleading and should be dropped or documented.

(I checked two things that turned out fine: `test_data/**` *does* make it into the wheel despite the
`absent from the packages configuration` warning, and `python setup.py --version` still prints only
`0.3.9` on stdout, so `pypi-publish.yml`'s version check still works.)

### 19. Global mutable config is not thread-safe *(observed)*

`config.py` keeps `_config` as a module-level dict; `override_config` / `override_configs` mutate it
process-wide and restore in `finally`. Concurrent or nested use interleaves badly —
`override_configs` in particular restores *every* key on exit, clobbering changes made by another
thread inside its scope. A `contextvars.ContextVar` would fix both.

### 20. Loop variables shadowing enclosing names *(observed)*

All currently benign (the iterables are evaluated before rebinding) but fragile:

- `tf2jax.py:838` — `for node in nodes:` nested inside `for node in graphdef.node:`
- `tf2jax.py:1402` — `for node, graph in _filter_nodes(_contains_custom_gradient, graph):` rebinds
  its own argument
- `mhlo.py:116` — `for dim in dim.get_vars():` inside `for dim in val.shape:`

### 21. `_extract_subgraphs` uses `[]` where it expects a possible miss *(observed)*

`tf2jax.py:791` does `grad_fn = library[grad_fn_name]`, and the next two lines handle
`if grad_fn is None: continue` ("The gradient is not available"). A name absent from `library`
raises `KeyError` rather than taking that path. `library.get(grad_fn_name)` matches the stated
intent.

---

## P5 — docs and release process

### 22. README CI badge has been red for months *(observed)*
It points at `ci.yml?branch=main`; it is the first thing on the project page.

### 23. `[TOC]` does not render on GitHub *(observed)*
`README.md:28` — a Google-internal markdown directive, shown literally on github.com.

### 24. `pypi-publish.yml` uses legacy PyPI credentials *(observed — worth verifying)*
It sets `TWINE_USERNAME`/`TWINE_PASSWORD` from `PYPI_USERNAME`/`PYPI_PASSWORD`. PyPI requires API
tokens (username literally `__token__`); if those secrets still hold a real username/password the
next release fails. Trusted Publishing (OIDC) would remove the secrets entirely. Separately,
`python setup.py sdist bdist_wheel` should become `python -m build`.

### 25. Version 0.3.9 is unreleased *(verified, informational)*
`tf2jax/__init__.py` says `0.3.9`; PyPI's latest is `0.3.8`.

---

## Suggested order of work

1. #1 flax pin — unblocks everything else (one line, verified).
2. #5 `fail-fast: false`, #6 action bumps, #4 failure notification — cheap, and they are why #1 went
   unnoticed.
3. #2 bound `jax` — stops the next recurrence.
4. #3 empty-`platforms` crash — one line, real user-facing bug.
5. #7 / #8 re-enable pytype and test-file pylint — both pass today; #7 needs the one annotation fix.
6. #13–#18 the small stuff — mechanical.
7. #9–#11 the coverage holes — the largest genuine gap, and the most design work.
