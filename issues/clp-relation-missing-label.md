# CLP relations with locally absent labels

## Finding

The v0.8 staging optimizer attempted to apply every interval-active experiment
CLP relation at every aligned global-axis point. For linked datasets whose local
matrix does not contain the relation source or target, `resolve_clp` raised a
`ValueError` while indexing the absent label.

The v0.7.4 reference explicitly checks that both labels occur in the local CLP
axis before applying a relation. The publication case study
`pub-2025-01-van_Stokkum_et_al` demonstrates this with the relations
`APC660t -> APC660b`, `APC660t -> APC660e`, `PC650t -> PC650b`, and
`PC650t -> PC650e` across linked datasets with different local components.

## Remediation and evidence

- Added the equivalent missing-label guard to v0.8 staging
  `glotaran/optimization/estimation.py`.
- Added a focused regression test proving that a relation with locally absent
  labels is skipped while the estimated CLP remains unchanged.
- Focused core test result: `2 passed`.
- The previously failing 22-dataset dry run and real fit subsequently pass.
- Definitive case-study evidence is under
  `validation/runs/case-studies/20260830-182522/` and its semantic report under
  `validation/comparisons/case-studies/20260830-182522/`.

The staging core change is intentionally uncommitted pending review. It is a
behavioral parity fix rather than result post-processing.
