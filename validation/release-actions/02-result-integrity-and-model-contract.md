# 2. Make sure the returned result describes the intended fit

Companion to action 2 in the [release report](../release-decision-report.md). Based on retained evidence and inspection of staging core `51574847` and reference core `8f26be01` on 6 September 2026.

The original action grouped three concerns together. They do not have equal severity: one is a confirmed result-construction defect; the other two concern model authoring and the public result contract.

## A. The optimizer's answer can differ from the returned parameters

An optimizer tries many parameter values. It also makes tiny temporary changes to estimate which direction improves the fit. At the end, it reports the parameter values it chose as its answer.

In current staging, each trial changes a shared parameter object. After optimization ends, the code builds the returned curves from that object without first putting back the chosen answer. Consequently, it can return the last tiny trial instead of the accepted parameter vector.

This is a confirmed defect in the spectral investigation. Its measured curve effect was only `9.5191e-10` normalized RMS, much smaller than the accepted spectral-guidance difference. **It does not explain that threshold crossing.** We have not measured its largest possible effect across other models. See the [full investigation](../../issues/spectral-guidance-current-tree.md).

### Where to look

- [Staging `Optimization.run`](../../temp/pyglotaran-staging-dev/pyglotaran/glotaran/optimization/optimization.py): `least_squares` returns `ls_result`. After the try/except, `o.calculate()` and `o.get_result()` build the output. There is no intervening restoration of `ls_result.x`.
- In the same file, `objective_function` calls `set_from_label_and_value_arrays`, which changes the shared parameters on every trial.
- [Reference `Optimizer.create_result`](../../temp/pyglotaran-main-dev/pyglotaran/glotaran/optimization/optimizer.py): look for `set_from_label_and_value_arrays` in result construction. This is the reference behavior to preserve, adapted to staging's architecture.
- [Staging optimizer tests](../../temp/pyglotaran-staging-dev/pyglotaran/tests/optimization/test_optimization.py): the appropriate place for a focused regression test.
- [Spectral diagnostic](../spectral_guidance_probe.py) and [its integration test](../tests/test_spectral_guidance_probe.py): evidence and diagnostic machinery. The existing trajectory test is not a regression test proving that production result restoration is fixed.

### Recommendation and release significance

Restore the accepted values through the existing parameter-setting API before recalculating the final residuals and constructing results. Avoid assigning raw numbers directly: the existing setter handles the optimizer's parameter representation. Preserve the separate zero-free-parameter and exception paths, where an ordinary accepted optimizer vector may not exist.

Test a deliberately distinguishable last trial versus accepted vector. Check returned parameters, reconstructed curve and residual, and the saved/reloaded result. Also keep zero-free-parameter behavior working. A targeted fake optimizer result can make the regression deterministic rather than relying on an accidental SciPy trial order.

**I recommend fixing this before release because the intended behavior is clear and the fix should be narrow.** If you accept the risk instead, record that decision separately with a tested impact bound. The existing tiny spectral measurement is evidence of small impact there, not a bound for every model.

## B. Artifact amplitudes can change kinetic normalization

The model stores starting populations of kinetic species together with amplitudes for coherent artifacts and oscillations. Kinetic normalization adds entries in that shared list. If artifact entries are included, they can make the kinetic populations too small.

For example, one kinetic population of 1 plus one artifact amplitude of 1 gives a sum of 2. Dividing by that sum halves the kinetic population, even though the artifact was not meant to be part of it. Free scales can compensate later, making the fitted curve look correct while reported scales change.

The migration converter already excludes the artifact/oscillation entries it adds. This solved the demonstrated migration issue. Native v0.8 authors must currently know to make those exclusions themselves.

### Where to look and what to do

- [Kinetic element](../../temp/pyglotaran-staging-dev/pyglotaran/glotaran/builtin/elements/kinetic/element.py): `normalization_sum` and `not_normalized_compartments`.
- [Converter](../case_studies/migrate.py), `activation`: creation of `non_kinetic_compartments` and the exclusion list.
- [Converter regression tests](../tests/test_case_studies.py): `test_convert_model_excludes_non_kinetic_amplitudes_from_normalization`.
- [Normalization brief](../../issues/kinetic-activation-normalization.md): full examples and possible API changes.

**My minimum recommendation is clear native-model documentation and a worked mixed kinetic/artifact example.** An automatic exclusion policy may be better, but it needs careful design: kinetic compartments owned by other elements can legitimately belong in the sum. Do not simply sum only the current element's species.

This need not block the already corrected migrated workflows. It becomes a release concern if v0.8 promises safe native authoring of these models without documenting the required exclusions. A redesign of the activation namespace can wait.

## C. Some diagnostics are derived rather than saved

v0.7 often saves a dataset scale of 1 and weighted RMSE explicitly. Some v0.8 results omit these defaults. Our comparison adapter supplies the default scale and calculates weighted RMSE from residuals and weights, recording that it derived them.

This is not currently evidence of wrong fitted curves. The question is whether users can obtain the diagnostics through the supported v0.8 API after saving and loading a result.

- [v0.8 compatibility loader](../compatibility/load_v08.py): default-scale and weighted-RMSE derivation.
- [Native objective/result data](../../temp/pyglotaran-staging-dev/pyglotaran/glotaran/optimization/objective.py): `create_result_metadata` and result serialization helpers.
- [Native `Result`](../../temp/pyglotaran-staging-dev/pyglotaran/glotaran/project/result.py): saving and validation/loading of optimization results.
- [Persistence brief](../../issues/weighted-rmse-persistence.md): the unresolved contract question.

**Recommendation:** decide which fields the public API promises and document how to retrieve them. If omission is intentional and the supported accessor reconstructs the value correctly, no v0.7-style file layout is needed. If a promised diagnostic is lost, fix its save/load path and test it. This is a blocker only to the extent that required downstream consumers cannot obtain information they need.
