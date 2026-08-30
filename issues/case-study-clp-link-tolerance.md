# Case-study CLP-link tolerance migration

## Finding

The v0.7 whole-cell notebook constructs its Scheme with
`clp_link_tolerance=2.1`, while the first v0.8 migration emitted the converter
default `0.1` in both experiments. The datasets use slightly offset wavelength
grids, so the smaller tolerance produced 2,926 conditionally linear parameters
instead of the reference 1,886 and changed the objective cost and SAS display.

The remaining apparent SAS mismatch after fixing the tolerance was a plotting
projection issue: v0.7 orders kinetic species from the initial-concentration
list, whereas v0.8 derives the order from the rate map. Label-aligned
concentration and SAS arrays were already numerically equal, but the notebook's
fixed color cycler assigned colors to different labels.

## Remediation and evidence

- The migrator detects numeric `Scheme(..., clp_link_tolerance=...)` arguments,
  associates them with the referenced model, rejects conflicting values, and
  emits the value on every migrated experiment.
- The external compatibility projection restores initial-concentration species
  order and removes duplicate suffixed kinetic compatibility variables.
- Final paired run: `validation/runs/case-studies/20260830-182522/` (3/3
  notebooks passed on both branches).
- Final comparison:
  `validation/comparisons/case-studies/20260830-182522/pub-2025-01-van-stokkum-et-al/comparison.json`.
- Whole-cell result: identical cost `512450.708544407`, identical 1,886 CLPs,
  1/1 function evaluations, and worst fitted-data normalized RMS
  `2.411819127175127e-8`.
- Fig. 7 reference and staging PNGs have identical dimensions and pixel values
  (486,356 pixels; zero differences). Label-aligned DA610 concentration and SAS
  normalized RMS differences are approximately `2.1e-16` and `5.7e-15`.

The repository remains provisionally `REVIEW_REQUIRED` because unrelated MCL
result leaves still exceed the primary fit tolerance; no scientific parity or
final difference classification is assigned here.
