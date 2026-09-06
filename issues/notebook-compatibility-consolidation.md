# Shared notebook compatibility consolidation

## Scope and implementation

The ignored `temp/case-studies` trees contain 12 source `_v08.ipynb` notebooks.
They carried multiple generations of embedded simulation, conversion, matrix
display, data-store and fit-report helpers. Historical copies under
`validation/runs` were also inventoried and retained as execution evidence.

The latest migration helper implementation now lives in the installable
`validation/notebook_compat/pyglotaran_compat` package. All 12 source notebooks
import it, and `validation/case_studies/migrate.py` emits those imports for future
migrations. `consolidate.py` updates existing notebooks without regenerating
their analysis cells. The inventory is trackable even though the notebooks are
ignored. Notebook-specific plotting functions remain analysis code.

The package retains native results, delegates simulation to the native engine,
and extends the extras result converter for validated legacy plotting consumers.
It supports v0.7 simulation dispatch and result passthrough without importing
v0.8-only extras conversion code. DataStore accepts Path objects as well as
strings and already loaded data; a complete disk-backed Project API is outside
this change. No optimizer, source model, parameter budget, tolerance or core
implementation was changed.

## Verification

- 31 validation tests passed in staging, including five new compatibility tests.
- Four applicable compatibility tests passed in the v0.7 environment; the v0.8
  result conversion test was deselected there.
- Editable installation succeeded in both temp validation environments and the
  workspace .venv-main/.venv-staging environments. An installable wheel
  was built under `validation/runs/compat-dist-20260906`.
- Fresh common runs: `validation/runs/{main,staging}/20260906-015900`, 11/11
  notebooks in each branch and 14/14 declared result leaves.
- All 14 fresh native common result leaves also passed direct conversion through
  the new package, with fitted-data agreement checked against native input minus
  residual. Report: `validation/runs/compat-common-conversion-20260906-02.json`.
  The preceding probe had a test-harness Dataset/DataArray error, corrected in
  the second probe without changing the adapter.
- Full consolidated case-study execution evidence is under
  `validation/runs/case-studies/compat-20260906-022006`. The source sidecar records
  package and notebook hashes; future runner manifests also hash the installed
  compatibility module.
- All 12 consolidated notebooks passed, including the four live simulation calls
  in the room-temperature publication notebook and the PFID workflow. The final
  `compatibility-verification.json` checks 2,896 artifact hashes with zero missing
  files, hash mismatches or notebook error cells. This is execution and adapter
  evidence; it does not reclassify prior case-study scientific differences.
- Real v0.8 simulation using a fresh fluorescence result's converted CLP and
  seeded noise agreed exactly with direct native simulation:
  `validation/runs/compat-simulation-20260906.txt`.
- The initial case-study run `compat-20260906-015928` was deliberately interrupted
  during the TA protocol after four notebooks had passed, to restart with one
  numerical thread. Completed evidence and an interruption record are retained.

## Current-tree parity caveat

The fresh common semantic report is
`validation/comparisons/v07-v08-20260906-015900.json`: 8 PASS,
5 EXPECTED_DIFFERENCE, 1 REGRESSION, no missing artifacts. Spectral guidance has
worst fitted-data normalized RMS `1.2572461877946428e-6` against `1e-6`.
Its common example notebook does not use the new compatibility package, and the
common input/core checkouts were not edited by this consolidation. This result
must not be presented as an acceptable parity rerun or silently reclassified.

A second fresh paired run with OMP/OPENBLAS/MKL/NUMEXPR thread counts set to one
also passed 11/11 notebooks per branch and reproduced exactly the same spectral
guidance RMS. Its report is `validation/comparisons/v07-v08-20260906-022046.json`.
Changing thread counts did not resolve this difference; root cause remains open.

Subsequent controlled investigation isolated the trigger to the current example
commits fixing `rates.k5`, `rates.k6`, and `scale.2`. Restoring only those vary
flags in memory reproduces the pinned baseline RMS exactly (`3.0325968790706684e-7`).
The constrained fit is sensitive to compartment ordering and numerical runtime;
matching both reproduces the native optimizer trajectory exactly. A smaller
staging accepted-parameter restoration defect was also identified, but does not
explain the threshold crossing. See [the full isolation evidence](spectral-guidance-current-tree.md).
The current-tree scenario remains `REGRESSION`; no production fix or tolerance
change was applied.

Actual reference/staging core revisions are respectively
`8f26be01d5a6ce63ec2556469ac3facc2d2cee68` and
`51574847bd5cd0e98a6c301f3d557d6d4ed85cd2`. Example revisions are
`409af6f4f5f1979b669a0729c0443600cf307b73` and
`4eed89efe8466b4e051fad7be8fcbf37b4c2a0b7`. These staging/example revisions have
moved beyond `scenarios.yml`; the contract was left intact.

The initial standard command failed before notebook execution because the
reference extras checkout (`96dbbbbc0cede1ecb932a202202cdf903a9894f8`) contains
Python syntax unsupported by its Python 3.10 interpreter. The successful rerun
used the existing unmodified plotting overlay at
`temp/case-studies/TestCaseInitConc/reference/_plotting_dependencies`, from pinned
extras revision `dcbe4baad5949768b65bf602d58018b5fe309f0a`, via PYTHONPATH.
Staging uses extras `700f9de482f317afa0339edc12314fd14699e459`.

Runtime benchmarking was not repeated: this extraction does not change the
public optimizer call, its work budget, or timed implementation. Nothing was
committed, and existing user changes were preserved.
