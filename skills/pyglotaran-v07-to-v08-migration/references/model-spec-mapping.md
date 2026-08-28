# v0.7.x to v0.8.x model-specification mapping

This reference is based on the v0.7.4 package at `8f26be01`, the v0.8 staging
package at `468c4cd5`, and the ported examples at the workspace’s pinned
example revisions. If a later staging revision changes a field, inspect its
Pydantic model and generated JSON schema before applying this mapping.

## New document shape

The v0.7 model is a global collection of named item sections. A typical v0.8
scheme has this shape:

```yaml
library:
  kinetic_model:
    type: kinetic
    rates:
      (s2, s1): kinetic.1
      (s3, s2): kinetic.2

experiments:
  exp1:
    residual_function: variable_projection
    scale:
      dataset1: scale.1
    datasets:
      dataset1:
        elements: [kinetic_model]
        activations:
          irf:
            type: gaussian
            compartments:
              s1: input.1
              s2: input.0
            center: irf.center
            width: irf.width
```

`Scheme.from_dict` requires `library` and `experiments`. `ModelLibrary` resolves
named library elements, and `ExperimentModel` resolves named `DataModel`
instances. The v0.8 source sets `extra="forbid"`, so unused legacy keys are
errors, not harmless metadata.

## Top-level and experiment mapping

| v0.7.x | v0.8.x | Migration rule |
| --- | --- | --- |
| `default_megacomplex` | no direct field | Give each library item an explicit `type`; do not preserve the default. |
| `dataset_groups.<group>` | `experiments.<experiment>` | Create one experiment for each independent v0.7 dataset group and move its datasets under it. |
| `dataset_groups.<group>.residual_function` | `experiments.<experiment>.residual_function` | Copy the value. The default remains `variable_projection`. |
| `dataset_groups.<group>.link_clp` | no direct field | v0.8 links the datasets inside an experiment. If `false` was intentional, split datasets into experiments and verify the numerical effect; do not silently discard the behavior. |
| `Scheme.clp_link_tolerance` | `experiments.<experiment>.clp_link_tolerance` | Move the setting into the experiment. |
| `Scheme.clp_link_method` | `experiments.<experiment>.clp_link_method` | Move the setting into the experiment. |
| `Scheme.maximum_number_function_evaluations` | `scheme.optimize(maximum_number_function_evaluations=...)` | Keep fit controls in Python, not the scheme YAML. |
| `Scheme.optimization_method`, `add_svd`, `ftol`, `gtol`, `xtol` | `scheme.optimize(...)` | Move these options to the fit call. |
| top-level `weights` | `experiments.<experiment>.datasets.<dataset>.weights` | Duplicate a weight entry under every dataset it used to name; remove its `datasets` list. |

If a v0.7 project has several dataset groups, keep the group boundary when
creating experiments. A single v0.8 experiment creates one linked optimization
data object for all its datasets.

## Library element mapping

### Kinetic/decay models

The common v0.7 pattern is:

```yaml
default_megacomplex: decay
megacomplex:
  complex1:
    k_matrix: [km1]
k_matrix:
  km1:
    matrix:
      (s1, s1): rates.k1
      (s2, s2): rates.k2
```

The v0.8 equivalent used by the staged examples is:

```yaml
library:
  complex1:
    type: kinetic
    rates:
      (s1, s1): rates.k1
      (s2, s2): rates.k2
```

Remove the `default_megacomplex`, `megacomplex`, and `k_matrix` indirection.
Keep tuple-like rate keys and their parameter labels. v0.8 also supports
`extends: [base]` on kinetic library elements; use it to express shared rate
maps such as the `base`/`cmplx1`/`cmplx2` transient-absorption example. Do not
flatten multiple v0.7 k-matrices without checking whether their matrices are
combined, alternative, or dataset-specific.

### Other elements

| v0.7 item | v0.8 library form | Important structural change |
| --- | --- | --- |
| decay/sequential/parallel megacomplex | `type: kinetic` | Put the rate matrix directly under `rates`. |
| damped oscillation megacomplex | `type: damped-oscillation` | Convert parallel `labels`, `frequencies`, and `rates` arrays into `oscillations: {label: {frequency, rate}}`. |
| coherent artifact megacomplex | `type: coherent-artifact` | Keep `order` and `width`; reference the element from the dataset’s `elements`. |
| CLP-guide workaround or megacomplex | `type: clp-guide` | Prefer the dedicated element with `target` and optional `dimension`; do not retain a fake 1x1 k-matrix. |
| baseline megacomplex | `type: baseline` | Put it in `library` and reference it in `elements`; inspect its target revision for plugin-specific fields. |
| PFID megacomplex | `type: pfid` | Convert parallel label/frequency/rate arrays to the v0.8 element’s `oscillations` mapping and put activation-specific data in the dataset. |
| spectral megacomplex | `type: spectral` | Convert its shape definitions to the v0.8 spectral element schema; do not confuse this with a kinetic model observed on a spectral global axis. |

Custom v0.7 megacomplex plugins require a corresponding v0.8 `Element` plugin.
Check its `type`, `dimension`, `data_model_type`, and JSON schema instead of
inventing a library shape.

## Dataset and activation mapping

| v0.7 dataset field | v0.8 dataset field | Notes |
| --- | --- | --- |
| `megacomplex` | `elements` | Rename the list and point at library labels. |
| `global_megacomplex` | `global_elements` | Keep global versus model contributions explicit. |
| `megacomplex_scale` | `element_scale` | Convert the old ordered list to a `{element_label: parameter_or_number}` mapping. |
| `global_megacomplex_scale` | `global_element_scale` | Same explicit mapping for global elements. |
| `initial_concentration` plus `initial_concentration.compartments/parameters` | `activations.<name>.compartments` | Zip the old two lists into a compartment-to-amplitude mapping. Ported examples use the name `irf`. |
| `initial_concentration.exclude_from_normalize` | `activations.<name>.not_normalized_compartments` | Preserve the compartment labels. |
| `irf: <name>` plus top-level `irf.<name>` | `activations.<name>` | Inline the IRF definition in the dataset. |
| `irf.<name>.type: gaussian` or spectral Gaussian | activation `type: gaussian` | Use `multi-gaussian` when multiple centers/widths are genuinely needed. |
| `irf.<name>.backsweep_period` | activation `backsweep` | The v0.8 field stores the backsweep period under the shorter name. |
| `irf.<name>.model_dispersion_with_wavenumber` | activation `reciproke_global_axis` | Preserve the exact v0.8 spelling used by the current source. |
| `force_index_dependent` | no direct field | Use actual v0.8 activation dispersion/shift fields when applicable; flag a case that only used the old force switch. |
| dataset `scale` | experiment `scale.<dataset>` | Move this scalar out of the dataset and into the experiment mapping. |

The activation syntax is a mapping, not the early staging prototype’s list:

```yaml
activations:
  irf:
    type: gaussian
    compartments:
      s1: inputs.1
      s2: inputs.7
    center: irf.center
    width: irf.width
```

For a v0.7 dataset with multiple elements, list all library labels in
`elements`. A CLP-guide element may not need an activation. A dataset must
still have a valid activation for the elements/data model that require one.

## Constraints, relations, penalties, and weights

### Element constraints

Move v0.7 top-level `clp_constraints` into the library element they constrain:

```yaml
library:
  target:
    type: kinetic
    rates: {...}
    clp_constraints:
      - type: zero
        target: s1
        interval: [[1, 1000]]
```

This is a real ownership change in v0.8. The staged fluorescence target model
demonstrates it. A constraint target may be a string or a list in current
staging; preserve the target semantics.

### Experiment penalties and relations

Move `clp_area_penalties` to the experiment and rename it to `clp_penalties`.
Keep `type: equal_area`, source/target labels, intervals, parameter, and weight.
Keep `clp_relations` at the experiment level with `source`, `target`,
`parameter`, and optional `interval`.

```yaml
experiments:
  exp1:
    clp_penalties:
      - type: equal_area
        source: s2
        target: s3
        source_intervals: [[100, 1000]]
        target_intervals: [[100, 1000]]
        parameter: area.1
        weight: 0.0016
    clp_relations:
      - source: s2
        target: s3
        parameter: rel.r1
        interval: [[0, 1000]]
```

### Dataset weights

The v0.7 form selects datasets centrally:

```yaml
weights:
  - datasets: [dataset2, dataset3]
    global_interval: [400, 600]
    value: 0.5
```

The v0.8 form puts the definition on each selected dataset:

```yaml
experiments:
  exp1:
    datasets:
      dataset2:
        weights:
          - global_interval: [400, 600]
            value: 0.5
      dataset3:
        weights:
          - global_interval: [400, 600]
            value: 0.5
```

Keep `model_interval` if it was present. Do not leave `datasets` inside a v0.8
weight item.

## Python and result API mapping

### v0.7 caller

```python
from glotaran.io import load_dataset, load_model, load_parameters
from glotaran.optimization.optimize import optimize
from glotaran.project.scheme import Scheme

data = {"dataset1": load_dataset("data/data1.ascii")}
model = load_model("models/model.yml")
parameters = load_parameters("models/parameters.yml")
scheme = Scheme(model, parameters, data, maximum_number_function_evaluations=18)
result = optimize(scheme)
```

### v0.8 caller

```python
from glotaran.io import load_parameters, load_scheme

scheme = load_scheme("models/scheme.yml", format_name="yml")
parameters = load_parameters("models/parameters.yml")
result = scheme.optimize(
    parameters=parameters,
    datasets={"dataset1": "data/data1.ascii"},
    maximum_number_function_evaluations=18,
)
```

v0.8 accepts dataset paths, xarray objects, or supported mappings at the fit
boundary. `scheme.load_data` is not the public migration path. The v0.8
`Scheme` has no v0.7 `model`, `parameters`, or `data` constructor payload.

Use `dry_run=True` and `verbose=False` for a first structural check. Access
native per-dataset output through `result.optimization_results["dataset1"]`.
Use `pyglotaran_extras.compat.convert(result)` only for code that still expects
the older result layout, especially plotting helpers.

## Validation and editor support

Generate a parameter-aware JSON schema when editing a port:

```python
from glotaran.io import load_parameters
from glotaran.utils.json_schema import create_model_scheme_json_schema

parameters = load_parameters("models/parameters.yml")
create_model_scheme_json_schema("schema.json", parameters)
```

Optionally add `# yaml-language-server: $schema=schema.json` to the scheme.
Then load the scheme and run a dry run in the v0.8 environment. Pydantic
validation catches forbidden legacy keys; optimization validation catches
unresolved parameter and element references.

For scientific parity, run the same initial parameters and comparable fit
budget on both versions. Compare input data exactly after canonicalization and
use fitted-data agreement as the primary metric. Treat differences in raw
parameters, CLP/matrix decompositions, result serialization, and labels as
secondary until reconstructed fitted data fails.

## Ported examples to consult

Use the staging examples as executable patterns, not as a universal converter:

- `ex_two_datasets/models/model.yml`: kinetic library, per-dataset
  activations, experiment scale, and renamed penalties.
- `study_fluorescence/models/global_model.yaml` and `target_model.yaml`:
  initial concentrations folded into activation compartments, backsweep rename,
  and target constraints moved into the kinetic element.
- `ex_doas_beta/models/scheme.yml`: damped-oscillation array-to-mapping
  conversion and separate kinetic/coherent-artifact elements.
- `study_transient_absorption/models/scheme_2d_co_co2.yml`: extendable kinetic
  library elements and dataset-specific elements/activations.
- `test/simultaneous_analysis_3d_weight/scheme.yml` and
  `test/simultaneous_analysis_6d_disp/scheme.yml`: dataset-local weights and
  dispersion activation fields.
- `ex_spectral_guidance/models/scheme_guidance.yml`: dedicated `clp-guide`
  element and experiment-level CLP relations/penalties.
