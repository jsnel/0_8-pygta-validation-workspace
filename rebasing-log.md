# Rebase log: staging onto main

Repository: `temp/pyglotaran-staging-dev/pyglotaran`

- Branch: `staging_rebased`, created from `origin/staging` at `afce5d50`
  ("Port main features to staging + additional minor improvements (#1609)").
- Onto: `origin/main` at `e6ba6316` ("Validation Workflow Update - Pin integration
  validation inputs (#1610)"); identical to `main` in `temp/pyglotaran-main-dev/pyglotaran`.
- Old merge base: `529a1b75` ("Combi update (#1363)").
- Scope: 176 linear staging commits (no merges) replayed onto 52 main-only commits.
- Command: `git rebase -i origin/main` with the default all-`pick` todo list.

## Resolution policy

- Main is the correct base; the end state of staging is validated. Intermediate
  staging bugs are left as-is.
- Each conflict is resolved with the smallest change that keeps the staging commit's
  intent and keeps main's independent changes where they do not touch the rewritten code.
- Files deleted by a staging commit stay deleted even if main modified them
  (modify/delete), because the staging end state does not contain them.
- Where main and staging edited the same lines, the staging commit's version wins for
  code the commit rewrites; main's version wins for dependency pins, CI and release
  metadata unless the staging commit explicitly changes the same item.
- No tests or examples are run until the rebase completes.

## Per-commit log

Format: `n/176 <original sha> <subject>`: result, then conflicted files and the side kept.

- 1/176 `bc975719` Implement model.item with pydantic.: conflicts.
  - `.pre-commit-config.yaml` (mypy `additional_dependencies`): combined. Main renamed
    `types-all` to `types-tabulate`; staging appended `pydantic`. Result:
    `[types-tabulate, types-attrs, pydantic]`.
  - `validation` submodule: kept main's pointer `7a729cad`. The staging commit moved it to
    an older pointer `e1137768`; main and the staging end state (`afce5d50`) both use
    `7a729cad`. This rule is applied to every later submodule-pointer conflict.
- 2-11/176 (`7b794f8f` .. `78991719`, `e735adad`, `7e9c8689`): applied cleanly.
- 12/176 `7e77d9e3` Remove old model and items.: conflicts.
  - modify/delete `glotaran/model/{dataset_group,dataset_model,model}.py`,
    `glotaran/model/test/test_dataset_model.py`: kept staging's deletion; main's
    edits to these files are dropped with them.
  - `glotaran/model/item.py`: staging hunks (file is rewritten; main's only change in the
    conflicting hunk was docstring spacing before `from __future__`, which the rewrite removes).
  - `setup.cfg`: staging removes the `glotaran.plugins.megacomplexes` entry-point block; kept
    the removal, which also drops main's added `pfid` entry point. All other main edits
    (authors, classifiers, numpy/pydantic/python pins, notebook extra) auto-merged and kept.
- 13-17/176 (`d464a2f9` .. `93e3df3b`, `a73b568e`): applied cleanly.
- 18/176 `8115364d` Adapt data provider.: conflict in `glotaran/optimization/data_provider.py`.
  Staging hunk kept (commit rewrites `DataProvider.__init__`; main's only change in that hunk
  removed a `# type:ignore[assignment]`). Main's other edits (blank line after module
  docstring, trailing comma, `groupby(..., squeeze=False)` / `to_numpy()` fix in `align_groups`)
  auto-merged and kept.
- 19-20/176 (`ac5e9153`, `f5a4fbef`): applied cleanly.
- 21/176 `72be2646` Created OptimizationMatrix: conflict in `glotaran/model/__init__.py`.
  Union: main's blank line after the module docstring plus staging's new `ClpConstraint` import.
- 22-31/176 (`930af5be` .. `44bca3cb`): applied cleanly.
- 32/176 `a2cfb942` Refactored simulation.: conflicts.
  - `glotaran/simulation/simulation.py`: staging hunk. The commit replaces
    `simulate_from_clp`/`simulate_full_model` with an `OptimizationMatrix`-based `simulate`;
    main's #1608 noise transpose fix lived in the removed code and is dropped here (the
    staging end state has its own seeded, dimension-sorted noise implementation from #1609).
    Main's blank line after the module docstring kept.
  - `glotaran/simulation/test/test_simulation.py`: staging version. Main's #1608 test
    (`test_simulate_full_model_same_result_when_swapping_global_and_model_megacomplex`) uses
    the removed `DatasetModel`/`SimpleTestModel` API and is dropped.
- 33-38/176 (`41363eeb` .. `5186489a`, `b61b5ec5`): applied cleanly.
- 39/176 `59efdeaa` Cleanup.: modify/delete only. Kept staging's deletion of
  `glotaran/analysis/__init__.py`, `glotaran/optimization/{estimation_provider,matrix_provider,optimize,optimizer}.py`.
  Main's edits to these files are dropped (including #1512 MatrixProvider ordering fix and
  estimation/optimizer updates); the staging replacements are `OptimizationMatrix`,
  `OptimizationEstimation` and `Optimization`.
- 40-42/176 (`4bbe6900`, `f4b1ffb0`, `a0948a4e`): applied cleanly.
- 43/176 `f94c6c00` Tempery deactivated mypy and darglint precommit checks.: conflict in
  `.pre-commit-config.yaml`. Kept staging's intent (flake8-docs hook commented out) with main's
  hook revision in the commented block (`rev: 7.1.1` instead of staging's `6.0.0`).
- 44-60/176 (`7b48327e` .. `28dae9af`): applied cleanly.
- 61/176 `6e947e61` Adapted coherent artifact.: modify/delete of
  `coherent_artifact_megacomplex.py`; kept staging's deletion (replaced by the new
  `coherent_artifact/megacomplex.py` in the same commit). Main's change there was a docstring blank line.
- 62/176 `8c944312` Adapdet damped oscillation megacomplex: modify/delete of
  `damped_oscillation_megacomplex.py` and `test/test_doas_model.py`; kept staging's deletion
  (replaced by `damped_oscillation/megacomplex.py` and a new test in the same commit). Main's
  #1513 fix (AttributeError for bad DOAS definitions) and its test are dropped with the old files.
- 63-64/176 (`7f2f45b1`, `3963a72f`): applied cleanly.
- 65/176 `a2359f39` Removed decay megacomplex: modify/delete of
  `decay/{decay_parallel_megacomplex,decay_sequential_megacomplex,initial_concentration,irf,k_matrix}.py`;
  kept staging's deletion.
  - Additional change (no textual conflict): removed main's `glotaran/builtin/megacomplexes/pfid/`
    (`__init__.py`, `pfid_megacomplex.py`, `test/test_pfid_model.py`, from #1510). It is written
    against the v0.7 API, imports `glotaran.builtin.megacomplexes.decay.irf` deleted by this
    commit, and the staging end state re-adds PFID as `glotaran/builtin/elements/pfid` in #1609.
    Leaving it would let later megacomplex->model->element directory renames carry it into
    `elements/` and collide with #1609. The `pfid` setup.cfg entry point was already dropped at 12/176.
- 66-70/176 (`0f9df734` .. `2b0fe3a4`): applied cleanly.
- 71/176 `682369da` Remove old scheme and result.: conflicts in `glotaran/project/result.py` and
  `glotaran/project/scheme.py`. Staging hunks (commit replaces both modules with the pydantic
  Scheme/Result); resolved files are identical to the original staging commit.
- 72-82/176 (`564e5c81` .. `ea593b4a`): applied cleanly.
- 83/176 `44970c08` Remove OptimizationGroup: modify/delete of
  `glotaran/optimization/optimization_group.py`; kept staging's deletion.
- 84-85/176 (`815134dc`, `968a42bf`): applied cleanly.
- 86/176 `290d42f6` Rename megacomplex plugins to models.: conflicts.
  - `glotaran/model/model.py`: staging's new module docstring ("This module contains the model.")
    plus main's blank line after it.
  - modify/delete `glotaran/plugin_system/megacomplex_registration.py`: kept staging's deletion
    (renamed to `model_registration.py`); main's only change was a blank line after the docstring.
- 87/176 `7182330c` Adapted scheme test.: conflict in `glotaran/plugin_system/base_registry.py`
  (`load_plugins`). Staging hunk (explicit plugin group list); main's Python 3.12
  `entry_points()` branch (#1437) in the same block is dropped. Main's `import sys` stays
  (now unused). Staging rewrites this function again in #1383.
- 88-97/176 (`8e00bc24` .. `75f2d081`): applied cleanly.
- 98/176 `be7a8d42` Remove generators,: modify/delete of `glotaran/project/generators/generator.py`;
  kept staging's deletion (main's change was a docstring blank line).
- 99/176 `46599017` Remove dataclass helpers.: modify/delete of `glotaran/project/dataclass_helpers.py`;
  kept staging's deletion (main's changes: blank line, `# type:ignore[arg-type]`).
- 100/176 `a2b41e89` Remove project.: modify/delete of `glotaran/project/project.py` and
  `project_{data,model,parameter,result}_registry.py`, `project_registry.py`; kept staging's
  deletion (main's changes: docstring blank lines, formatting).
- 101/176 `1fadbab4` Remove benchmark.: applied cleanly (main had already removed asv in #1511).
- 102/176 `deb8243a` Remove cli.: conflicts.
  - modify/delete `glotaran/cli/{commands/explore.py,main.py,test/test_cli.py}`: kept staging's deletion.
  - `requirements_dev.txt`: main's current pins, with staging's intent applied (removed the
    `click==8.3.1` line). `setup.cfg` removal of `click>=8.1.3` auto-merged.
- 103-105/176 (`04b2fca1`, `4b62a7a8`, `ccd95c1c`): applied cleanly.
- 106/176 `1c4e05a6` Cleanup.: modify/delete of `glotaran/utils/test/test_io.py`; kept staging's
  deletion (main's change was a docstring blank line).
- 107-129/176 (`c930100f` .. `c648185f`): applied cleanly.
- 130/176 `cf66ce68` Final mypy fixes.: conflict in `.pre-commit-config.yaml`, hook `rev` bumps
  only (pre-commit-hooks, pyupgrade, black, mypy, rstcheck, codespell). Kept main's newer revs.
  Staging's other changes in the file (commenting out the pygrep `python-*` hooks) auto-merged.
- 131-133/176 (`c58222d1`, `6b1b7517`, `1aa3d6a2`): applied cleanly.
- 134/176 `a2211d6f` Fix clp constraints (#1366): conflict in `.pre-commit-config.yaml` (codespell
  hook). Union: main's `additional_dependencies: [tomli]` (reads `[tool.codespell]` from
  pyproject.toml) plus staging's `args: --ignore-words-list=glotaran,doas,projectio` (the form
  the staging end state uses).
- 135-137/176 (`d4ccfc4d`, `e1ca87cc`, `3b68893e`): applied cleanly.
- 138/176 `26f45f42` 0.8/pydantic2 fix (#1378): conflicts in `requirements_dev.txt` and `setup.cfg`.
  Both sides already require pydantic 2; kept main's newer pins (`pydantic==2.12.5`,
  `pydantic>=2.7.2` and the other main runtime pins). Staging's code changes auto-merged.
- 139/176 `8a564bb6` Use ruff as linter (#1379): conflicts.
  - `.pre-commit-config.yaml`: per hunk. black and mypy `rev`: main's newer revs. Linter block:
    staging (yesqa + flake8 replaced by `ruff-pre-commit` / `ruff`), which drops main's flake8
    `rev: 7.1.1` bump for the removed hook.
  - `glotaran/utils/io.py`, `glotaran/builtin/io/pandas/{csv,xlsx}.py`: staging hunks. Staging
    changes `safe_dataframe_fillna`/`safe_dataframe_replace` to return a new DataFrame and updates
    the callers; this supersedes main's pandas-3 fix (#1607), which assigned the column in place.
    Main's other io.py edits (`Generator[Path]`, str clp labels in error message) auto-merged.
  - `glotaran/io/prepare_dataset.py`: combined. Staging's renamed SVD variables
    (`lsv, sv, rsv`) with main's #1520/#1608 call
    `np.linalg.svd(data_array.transpose(lsv_dim, rsv_dim).to_numpy(), ...)`. This line is
    identical to the staging end state.
  - `glotaran/typing/types.py`: staging hunks (`from __future__ import annotations`,
    `# noqa: F401`), with main's blank line after the module docstring.
- 140/176 `af9b42c5` Change Parameter from attrs to pydantic (#1381): conflicts.
  - `glotaran/parameter/parameter.py`: staging hunks (attrs `Parameter` replaced by pydantic).
    Main's #1607 `nan_repr_to_none` converter for `expression` was attached to the removed attrs
    field and is dropped. Resolved file is identical to the original staging commit.
  - modify/delete `glotaran/utils/attrs_helper.py`: kept staging's deletion.
  - `.pre-commit-config.yaml` mypy deps: staging drops `types-attrs`, main renamed `types-all` to
    `types-tabulate`; result `[types-tabulate, pydantic]`.
  - `requirements_dev.txt`: main's pins with staging's intent applied (removed `attrs ==25.4.0`).
- 141-143/176 (`40b3d5ef`, `ace4db8b`, `719a2d51`): applied cleanly.
- 144/176 `8ee4c583` Create useful schema (#1385): conflict in `glotaran/model/__init__.py`.
  Staging reduces the module to its docstring; kept that (drops main's blank line together with
  the removed imports). Identical to the original staging commit.
- 145/176 `8c88c3b2` Move tests to a dedicated tests folder (#1386): conflicts.
  - `.github/workflows/CI_CD_actions.yml`: combined. Main's `uv run pytest ...` command with
    staging's test path `tests` (instead of `glotaran`).
  - `.pre-commit-config.yaml` mypy hook: staging's `exclude: "docs|benchmark/|tests/.*"` with
    main's `[types-tabulate, pydantic]`.
  - Additional change (no textual conflict): main-only `glotaran/io/test/test_prepare_dataset.py`
    (#1520/#1608) moved to `tests/io/test_prepare_dataset.py`, and main-only
    `glotaran/io/test/__init__.py` removed (staging adds `tests/io/__init__.py`). This follows the
    commit's intent of moving all tests out of the package; git did not move this file because
    the directory did not exist on staging. The staging end state has its own
    `tests/io/test_prepare_dataset.py` from #1609.
- 146/176 `9d5d44e6` Use hatch as build system (#1392): 17 conflicts. Rule used for this commit:
  where staging moves content to a new file or format (setup.cfg metadata -> pyproject
  `[project]`, `requirements_dev.txt` -> `requirements_pinned.txt`, `docs/requirements.txt` ->
  `[docs]` extra, rst -> md docs), the staging version is kept as committed and main's deltas to
  the old files are listed under "Post-rebase follow-ups" below instead of being ported mid-rebase.
  - modify/delete, deleted by staging, kept deleted: `AUTHORS.rst`, `MANIFEST.in`,
    `docs/requirements.txt`, `docs/source/index.rst`, `docs/source/installation.rst`,
    `requirements_dev.txt`, `tox.ini`.
  - modify/delete, deleted by main (#1511 removed asv/binder, #1540 replaced the quickstart
    notebook), kept deleted: `.github/workflows/pr_benchmark.yml`,
    `.github/workflows/pr_benchmark_reaction.yml`, `binder/environment.yml`,
    `docs/source/notebooks/quickstart/quickstart.ipynb`.
  - `docs/source/index.md` (new in this commit, converted from index.rst): applied main's
    one-line #1540 change `notebooks/quickstart/quickstart` -> `notebooks/getting_started/getting_started`,
    because the quickstart notebook no longer exists on this branch.
  - `setup.cfg`: staging (metadata/options removed, only tool sections such as `[flake8]` remain).
  - `pyproject.toml`: removed `[tool.check-manifest]` (staging); kept main's `[tool.codespell]`
    and added staging's `[tool.interrogate]` / `[tool.nbqa.addopts]` (union, blank line between).
  - `.pre-commit-config.yaml`: staging removes the rstcheck hook (docs moved to md); kept removal,
    which drops main's rstcheck `rev: v6.2.4`. Other staging changes (pyproject-fmt, actionlint,
    setup-cfg-fmt removal) auto-merged.
  - `docs/source/conf.py` intersphinx `python` entry: both sides fixed it; kept staging's
    `https://docs.python.org/3`.
  - `.github/workflows/CI_CD_actions.yml`: main's uv tooling (setup-uv, `uv pip list`,
    `uv run pytest`, `uv build`, `pypa/gh-action-pypi-publish@v1.13.0`) auto-merged or kept;
    staging's changes applied in uv form: check-manifest job removed (and its `needs:` entry),
    docs jobs install `".[docs]"`, docs-notebooks installs `-r requirements_pinned.txt ".[docs]"`
    (main's `conda install -y pandoc` kept), test job installs `-e ".[test]" -r requirements_pinned.txt`,
    deploy job gains staging's `environment: pypi`. Staging's `pip install -U hatch` / `hatch build`
    replaced by main's existing `uv build` (works with the hatchling backend).
  - `.github/workflows/integration-tests.yml`: main's `uv pip install .` with
    `-r requirements_pinned.txt` instead of the deleted `requirements_dev.txt`.
- 147/176 `662d2d5c` Use ruff for formatting (replaces black, isort and nbqa) (#1396): conflicts.
  - 11 Python files (`docs/remove_notebook_written_data.py`, `glotaran/__init__.py`,
    `glotaran/{builtin,deprecation,io/preprocessor,parameter,simulation,typing}/__init__.py`,
    `glotaran/testing/simulated_data/shared_decay.py`, `glotaran/utils/regex.py`,
    `tests/deprecation/dummy_package/__init__.py`): staging inserts
    `from __future__ import annotations` directly after the module docstring where main had added
    a blank line. Result: docstring, blank line, `from __future__ import annotations`.
  - `.pre-commit-config.yaml`: black/isort and nbQA blocks removed (staging, replaced by ruff
    hooks); mypy `rev` kept at main's v1.11.2.
  - Observation (no conflict): `glotaran/__init__.py` carries main's `__version__ = "0.7.4"`.
    The merge base had `0.8.0.dev0`, main changed it in its release commits, staging never touched
    the line, so main's value auto-merged at the start of the rebase. Listed as a follow-up.
- 148/176 `bfd4fa7c` Add unit test for link_clp: applied cleanly.
- 149/176 `065ee43e` Fix linked clp result creation (#1418): conflict in
  `glotaran/optimization/data.py` (`align_groups` signature). Staging hunk (adds `datasets`
  parameter and `group_sizes` return); main's change there was only a trailing comma.
- 150-151/176 (`5f160900`, `491a7b65`): applied cleanly.
- 152/176 `60f9c7cd` Use element plugin registry to define LibraryType (#1427): conflict in
  `.pre-commit-config.yaml`, mypy `rev` (staging v1.8.0 vs main v1.11.2); kept main's newer rev.
- 153/176 `87f9303c` Autoupdate pre-commit config staging (#1438): conflicts.
  - `.pre-commit-config.yaml`: pyupgrade and mypy `rev`; kept main's newer revs (v3.17.0, v1.11.2).
  - `tests/deprecation/modules/test_glotaran_root.py`: staging's docstring (trailing space removed).
- 154/176 `bc5679ad` Staging fix relations (#1455): applied cleanly.
- 155/176 `4cd51f1e` Use pyglotaran-examples@staging_rewrite for CI integration tests (#1462):
  conflict in `.github/workflows/integration-tests.yml`. Staging's purpose (run the 0.8 examples
  from `staging_rewrite`) contradicts main's #1610 pinning of the v0.7 examples, so:
  - staging: `glotaran/pyglotaran-examples@staging_rewrite` (both jobs), `examples_branch:
    staging_rewrite` (replaces main's `install_extras: false`), "Upload Example Notebook Artifact"
    step with `if: always()`, results path `~/pyglotaran_examples_results_staging`.
  - main: SHA-pinned actions (checkout, setup-python, setup-uv, upload/download-artifact,
    delete-artifact), `uv pip install`/`uv pip list`, "bundle" spelling, and the #1610
    compare-results job (pinned v0.7 gold standard `5effc75`, validator from the submodule).
  - Additional change: removed main's two "Checkout pinned examples" steps
    (`ref: fcfe1519...`, plus their comment). They pre-populate `pyglotaran-examples` with the
    v0.7 notebooks and would override the `staging_rewrite` checkout. The staging end state has
    no such steps.
- 156/176 `7aa933f0` Remove test of upstream schema creation functionality (#1464): applied cleanly.
- 157/176 `11e359a3` Add official Python 3.12 support (#1459): conflict in
  `.github/workflows/CI_CD_actions.yml` test matrix. Kept staging's `["3.10", "3.11", "3.12"]`,
  matching this branch's `requires-python = ">=3.10,<3.13"` in `pyproject.toml` (main's 3.13/3.14
  support lived in the setup.cfg metadata not ported at 146/176; listed as a follow-up).
- 158/176 `9afaf1ad` Combined updates (#1472): `validation` submodule conflict; kept main's `7a729cad`
  (standing rule from 1/176). Other changes auto-merged.
- 159-163/176 (`898e6d74` .. `eee32699`): applied cleanly.
- 164/176 `7654854e` Fix pre-commit config issues (#1518): conflict in `.pre-commit-config.yaml`
  mypy deps; staging's `[types-tabulate, numpy, pydantic]` (superset of main's `[types-tabulate, pydantic]`).
- 165/176 `76fb0554` Bump the gh-actions group with 3 updates (#1488): conflict in
  `.github/workflows/CI_CD_actions.yml` (`pypa/gh-action-pypi-publish` v1.9.0 vs main v1.13.0);
  kept main's newer version. Its other bumps were already on main, so the resolved commit was
  empty and git dropped it.
- 166/176 `5517c7a1` Bump actions/github-script from 6 to 7 (#1491): modify/delete of
  `.github/workflows/binder-on-pr.yml` (removed on main in #1511); kept main's deletion. The commit
  becomes empty and is dropped (its only change was to that file).
- 167/176 `e73f940b` Bump github/codeql-action from 2 to 3 (#1492): no conflict but empty (main
  already uses codeql-action v3); skipped with `git rebase --skip`.
- 168/176 `ba2ba85f` Bump actions/upload-artifact from 3 to 4 (#1490): no conflict but empty (main already has this change); skipped.
- 169-171/176 (`05bb1cad`, `4044f844`, `f21ca65d`): applied cleanly.
- 172/176 `2ef4ceab` Fix prepare_dataset's add_svd_to_dataset function (#1522): conflict in
  `glotaran/io/prepare_dataset.py`. Staging's `np.linalg.svd(data_array.data, ...)` vs main's
  `np.linalg.svd(data_array.transpose(lsv_dim, rsv_dim).to_numpy(), ...)` (#1520/#1608, already
  merged at 139/176). Kept main's line, which is also the staging end state. The commit becomes
  empty and is skipped.
- 173/176 `a5fdc387` Bump numpy from 1.26.4 to 2.0.1 (#1523): conflict in `glotaran/utils/io.py`
  (`create_clp_guide_dataset` error message). Both sides convert labels to `str`; kept staging's
  `dataset.clp_label.to_numpy()` form.
- 174/176 `06d4c981` Bump the runtime-dependencies group across 1 directory with 2 updates (#1525):
  applied cleanly.
- 175/176 `7efc9d11` Complete internal rewrite - new result API (#1562): conflicts.
  - `.pre-commit-config.yaml`: pre-commit-hooks, pyupgrade, mypy, codespell `rev`; staging's revs
    are now newer than main's (v6.0.0, v3.21.2, v1.19.0, v2.4.1) and the commit bumps them
    explicitly; kept staging's.
  - `docs/source/conf.py`: main's dynamic copyright year (`current_year = datetime.now().year`)
    with staging's `# noqa: A001` appended to the `copyright` line.
  - `glotaran/builtin/io/yml/utils.py`: staging's docstring ("Defaults to 2.").
  - `glotaran/plugin_system/base_registry.py`: staging's imports (drops `Iterable` and the
    `import sys` that main added and that has been unused since 87/176).
- 176/176 `afce5d50` Port main features to staging + additional minor improvements (#1609): conflicts.
  - `.github/workflows/integration-tests.yml`: staging's step name ("... pinned validation
    action") and "v0.7.4 gold standard" comment; main's SHA-pinned `actions/checkout`.
  - `docs/source/conf.py` `linkcheck_ignore`: main's regex
    `stackoverflow\.com/a/(65375904|47663099)/3990615` (superset of staging's single URL).
  - `glotaran/parameter/parameters.py` (`param_dict_to_markdown`): staging hunk (port of main's
    near-zero standard-error handling via `MINIMUM_STANDARD_ERROR`, without mutating the parameter).
  - `changelog.md`: staging's entries for the port. Earlier auto-merges had put main's
    `0.7.5 (Unreleased)` header on top and dropped staging's two deprecation subheadings; restored
    staging's `(changes-0_8_0)= / 0.8.0 (Unreleased)` header and the "Deprecations (due in 0.9.0)" /
    "Deprecated functionality removed in this release" subheadings. Main's 0.7.2, 0.7.3 and 0.7.4
    release sections and release dates are kept below it.
  - add/add `tests/io/test_prepare_dataset.py`: staging's version (the end state). It ports the
    main test moved at 145/176 and covers the same behaviours (expected variables, transposed
    input, custom name/dims/data array, no recomputation).

## Result

- `staging_rebased` = `fabe2943`, 171 commits on top of `origin/main` (`e6ba6316`). 176 picked;
  5 became empty because main already contained the change and were dropped: 165 `76fb0554`,
  166 `5517c7a1`, 167 `e73f940b`, 168 `ba2ba85f`, 172 `2ef4ceab`.
- `git diff origin/staging staging_rebased`: 26 files. `glotaran/` and `tests/` are identical to
  the staging end state except `glotaran/__init__.py` (`__version__`) and one blank line in
  `glotaran/parameter/parameters.py`. The remaining differences are main-side: CI workflows
  (uv, SHA pins, dependabot config, binder workflows removed), `.gitignore`, README, `INSTALLATION.md`,
  `NOTICE.md`, getting-started notebook replacing quickstart, binder removal, docs `conf.py`
  (binder prolog removed, authors, copyright year), changelog 0.7.2-0.7.4 history,
  `[tool.codespell]` and codespell `tomli`.
- Not pushed. No commits were made outside the rebase.

## Verification

- Core tests, run after the rebase in a throwaway venv (scratchpad; same 157 package versions as
  `temp/pyglotaran-staging-dev/.venv`, numpy 2.0.1, scipy 1.14.1, xarray 2024.7.0, Python 3.10.19)
  with an editable install of this checkout:
  - `staging_rebased`: 455 passed, 9 xfailed.
  - `origin/staging` (same venv): 454 passed, 9 xfailed, 1 failed (`test_glotaran_version`). The
    failure is an environment artifact: the editable-install metadata was built while the checkout
    reported `0.7.4`, so it does not match `origin/staging`'s `0.8.0.dev0`.
- The shared `temp/pyglotaran-staging-dev/.venv` was not used for the run: its editable-install
  metadata comes from `feature/scale_list` and registers entry points
  (`glotaran.builtin.io.hamamatsu.img_file_reader`) that do not exist on this branch.
- The validation notebooks were not run. Because `glotaran/` is identical to `origin/staging`
  apart from the version string, numerical results are expected to match `origin/staging`.

## Post-rebase follow-ups (not changed during the rebase)

1. `glotaran/__init__.py`: `__version__ = "0.7.4"` (from main); staging uses `"0.8.0.dev0"`.
2. Main's setup.cfg metadata was not ported into pyproject `[project]` at 146/176: author
   Sebastian Weigand, `python_requires <3.15` and 3.12-3.14 classifiers (branch has `<3.13`),
   `numpy <2.4` (branch has `<2.1`), `notebook` extra (`ipykernel>=6.23.1`, `jupyterlab>=4.0.0`)
   and `full` including it. The CI test matrix stays at 3.10-3.12 to match.
3. Main's newer pins in the deleted `requirements_dev.txt` were not carried into
   `requirements_pinned.txt` (e.g. numpy 2.2.6/2.3.5, scipy 1.15.3/1.16.3, xarray 2024.11.0/2025.12.0).
4. Main's docs content changes not carried into the md conversions: AUTHORS.rst rewrite (core team,
   core publications) vs `AUTHORS.md` / `docs/source/authors.md`; installation.rst rewrite and root
   `INSTALLATION.md` vs `docs/source/installation.md`; `docs/requirements.txt` addition
   `pyglotaran_extras>=0.7.0` vs the `[docs]` extra.
5. Main fixes dropped with deleted v0.7 files whose port is not mentioned in the staging changelog:
   #1513 (AttributeError validating a bad DOAS definition, plus its test). #1512, #1591, #1607 and
   #1608 are listed as ported in the #1609 changelog entries.
6. `docs/source/notebooks/plugin_system/plugin_howto_write_a_io_plugin.ipynb` still refers to
   "the example data from the quickstart" in prose; the quickstart notebook is gone.
