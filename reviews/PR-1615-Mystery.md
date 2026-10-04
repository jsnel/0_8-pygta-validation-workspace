# Review: glotaran/pyglotaran#1615 — Project API (record / recompute / compare / export)

**Scope reviewed:** full diff `origin/staging_rebased...origin/staging_rebase_with_project` (17 commits, +3469/−95), read against `project-api-proposal.md` first, then cross-checked against the PR description and `project-api-implementation.md`. Both documents' claims check out against the code wherever I verified them (see "Commands run" below).

**Overall:** the implementation is faithful to the specification, well tested (521 passed / 9 xfailed locally), and the prerequisite behavior changes are done cleanly. I found **no blocking issues**. Findings below are should-fix at most.

## Findings

### 1. `project.export` leaves `result.source_path` (and array attrs) pointing at a deleted temp folder — *should fix*
`export.py:103` saves into `.{name}.{pid}.tmp` and renames at `export.py:123`. `Result.save` defaults `update_source_path=True`, so `save_result` sets `result.source_path` to the temp path (`project_io_registration.py:411`) which no longer exists after the rename. Reproduced:
```
result.source_path after export: ...\exports\.exp1.23564.tmp   (exists: False)
```
The in-memory `residuals`/element datasets also get `attrs["source_path"]` into the temp folder via `save_dataset(update_source_path=True)` (`objective.py:328`). The on-disk export is correct; this is an in-memory wart, but it breaks the "source_path points at where the result was saved" invariant and can confuse follow-up code. **Fix:** pass `update_source_path=False` through `result.save(...)` kwargs in `export_result`, or set `result.source_path = folder` after the rename. Relatedly, the comment at `export.py:100` ("Before saving, which sets the source path of the scheme to the saved file") is stale — the PR itself stopped that mutation in `result.py:203`.

### 2. YAML written UTF-8 but read with the locale encoding — records/exports corrupt or crash on Windows — *should fix* (pre-existing root cause, newly surfaced)
`utils.py:63` (`load_dict`) opens files with no encoding; `write_dict` (line 47) writes `encoding="utf8"`. On Windows with Python < 3.15 (this repo supports 3.10–3.14; the venv reports cp1252), a `record.yml`/`export.yml` containing non-ASCII text (user-supplied `name`, an exception message) round-trips corrupted. Reproduced: `name: ΔA α-helices β₂` reads back as mojibake; `name: Ё test` raises `UnicodeDecodeError: 'charmap' codec can't decode byte 0x81` — the record is then skipped as "damaged" by `list_results`, and `recompute`/`compare_results` crash. **Fix:** `Path(source).open(encoding="utf8")` in `load_dict` (the PR already touches this file) plus a non-ASCII round-trip test.

### 3. "Optimization failed" warning now points at library internals — *minor*
`optimization.py:154` uses `stacklevel=3`, but the new `_prepare_optimization`/`_run_optimization` split (`scheme.py:102`) added a frame, so the warning cites `glotaran/project/scheme.py:102` (or `project.py:156`) instead of the user's call. Reproduced with plain `scheme.optimize`. Affects non-project users too. **Fix:** compute the stacklevel by skipping glotaran frames, or adjust to the new depth.

### 4. Failed-fit `nfev` inconsistent between record and export — *minor*
For a gracefully-failed fit, `record.yml` correctly reports `number_of_function_evaluations = len(cost_history)` (3 in my repro), but `export.yml` (via `summarize_fit` → `info.py:179`) reports `1` — the parameter-history record count, meaningless with `verbose=False`. Root cause pre-exists; the PR surfaces it in `export.yml`. Since `cost_history` now always exists, `Optimization` could pass its length for the failed case.

### 5. `compare_results(result, result.record)` shows a spurious `converged` difference — *minor/question*
`fit_from_result` calls `summarize_fit(result)` without `converged` (`compare.py:170`), so comparing a result with its own record shows `converged: None → True`; the test works around it by dropping the row. Consequence of the deliberate decision not to touch `OptimizationInfo` — flagging so it's a conscious choice.

### 6. Damaged/hand-edited metadata gives raw or misleading errors — *minor*
`recompute` on a malformed `record.yml` raises a raw ruamel `ParserError`; an empty `record.yml` raises `TypeError` (`dict(None)`); a hand-edited `result.yml` in an export raises `KeyError` in `read_export_files`. And `list_records` reports a *newer schema version* record as "damaged" (`compare.py:103` catches the clear `ValueError` from `read_record_file` and relabels it). Listing behavior matches the spec ("skipped with a warning"); only `recompute`/`compare` error quality is affected. Suggest wrapping in `GlotaranUserError` with the folder and cause.

### 7. Unrelated validation-threshold relaxation bundled into the PR — *question (process)*
Commit `2d075c21` bumps the `validation` submodule to relax the `ex_spectral_guidance` acceptance threshold (2e-6 → 3e-6). It is unrelated to the Project API and is not mentioned in the PR description; a squash merge will fold it into the feature commit. The rationale exists in the submodule commit, but consider splitting it out or at least mentioning it in the description.

### 8. Smaller items
- `export.py:96`: temp name uses pid only — two threads in one process exporting the same name share the temp folder. Edge case.
- `export.py:147-152`: if `result.record` is set but the record folder was deleted, `export.yml` keeps the stale `record_id` while `source` is freshly detected — mixed provenance. Edge case.
- `OptimizerSettings` (`info.py:32`) does not record `add_svd`; recomputing a fit run with `add_svd=False` produces extra SVD arrays (drift check only covers cost/RMSE, so it passes silently). The spec's optimizer list excludes it — noting as spec-silent behavior, not a defect.
- Forward compatibility: `result.yml` written by this branch carries `optimizer_settings` (and `recomputation`), which older v0.8 dev builds refuse to load (`Result` is `extra="forbid"`). Fine pre-release; the reverse direction (old files in new code) works — verified.
- Docs: the getting-started notebook says "`Project.start()` without an argument uses the folder of the notebook" — it's the *working directory* (in Jupyter these can differ). `project.md` states it correctly.

### Coverage gaps (behavior I verified manually but that tests would not catch breaking)
- Multi-experiment/multi-dataset fits through a project, including the repeated-label warning (`record.py:291`) — verified working (warning fires, record written, recompute reproduces cost).
- Recompute of *failed/interrupted* records — verified working (evaluates at the raising parameters; `standard_errors` are `nan`, no crash).
- `list_results(scheme_source=...)` filter; live VS Code/Jupyter source detection (acknowledged in the PR).

Everything else I probed and could *not* confirm as a defect: deep-copy isolation (test `test_optimize_result_does_not_share_inputs` is solid), dry-run statistics, the YAML indent fix, csv round-trip precision (tested at 1e-15), atomic `record.yml` replace, exclusive folder claiming under two processes, `verbose` forwarding (the stray SciPy table in my console was the import-time fit in `sequential_spectral_decay.py:47`, pre-existing), and pyglotaran-extras compatibility (`convert_result_dataset.py` already handles Dataset `input_data`).

## Spec items not implemented
None missing. All "Not in v0.8" items are correctly absent (no lineage, no recording args on `Scheme.optimize`, no env vars, no parent search, no `input_data=False`, no `Parameters.diff`/`Scheme.diff`). Prerequisites 1, 2, 4, 5 are implemented; prerequisite 3 is documented as accepted. The one deviation (filter-removal instead of the spec's `force_write_input_data` context flag) is documented in both the implementation note and the PR description and is behaviorally equivalent.

## Commands run
- `git fetch origin`; diff/log inspection of `staging_rebased...staging_rebase_with_project` (17 commits).
- `pytest -q -p no:cacheprovider tests` from the pyglotaran folder with the staging venv: **521 passed, 9 xfailed** (20 s).
- `uvx ruff@0.14.7 check glotaran tests`: **pass**; `uvx ruff@0.14.7 format --check glotaran tests`: **pass** (208 files).
- `pre-commit run --all-files` (incl. mypy, interrogate, codespell): **all passed**.
- Nine reproduction scripts in a scratch dir outside the repo (since deleted): export `source_path` dangling (confirmed), failed/interrupted fit records + recompute (work), damaged/v2-schema records (skip-with-warning in listing; raw errors in recompute), old-format `result.yml` loads (works; `optimizer_settings=None`), unicode name round-trip (mojibake/`UnicodeDecodeError` confirmed), two-experiment repeated-label fit + recompute (works), failed-fit export summary inconsistency (confirmed), warning stacklevel (confirmed).
- Verified the cited validation report `validation/comparisons/v07-v08-20261004-181627.json`: 8 PASS / 6 EXPECTED_DIFFERENCE / 0 REGRESSION / 0 BASELINE_FAILURE — as claimed.
- Working tree left untouched (`git status` clean before and after; scratch files deleted).

## Areas not reviewed
- Execution of the getting-started notebook / docs build (per instructions); reviewed the diff only.
- The `pyglotaran-examples` companion branch (separate repo, not in this diff).
- Real VS Code/Jupyter source detection and a real kernel kill (unit-tested only, acknowledged by the author).
- Cross-machine/version recompute agreement and the PFID benchmark (acknowledged as open by the author).
- The internals of the `validation` submodule beyond the pin diff shown above.