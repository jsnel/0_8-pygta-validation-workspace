---
name: pyglotaran-v07-to-v08-migration
description: Migrate pyglotaran v0.7.x model YAML, parameter references, notebooks, and fitting calls to the v0.8.x library/experiments scheme API. Use when a user has legacy `default_megacomplex`, `dataset_groups`, `megacomplex`, `k_matrix`, `initial_concentration`, `irf`, or `dataset` specifications, or asks to port a v0.7 model, example, or result workflow to v0.8.
---

# Pyglotaran v0.7 to v0.8 migration

Use this skill to produce a v0.8 scheme that preserves the v0.7 model’s
labels, parameter meanings, dataset grouping, and numerical intent. Treat the
v0.8 format as a new typed schema, not as a collection of spelling aliases.

## Workflow

1. Establish the source and target versions. Inspect the v0.7 model, parameter
   file, data labels, notebook/script, and the exact v0.8 package source or
   environment. In the validation workspace, use
   `temp/pyglotaran-main-dev` for v0.7.4 and `temp/pyglotaran-staging-dev` for
   v0.8 staging. Read [model-spec-mapping.md](references/model-spec-mapping.md)
   before editing.

2. Inventory every legacy section and its semantic role. Record dataset group
   membership, local/global elements, scales, initial concentrations, IRF
   details, constraints, relations, penalties, weights, and any custom plugin
   types. Preserve labels and parameter expressions exactly unless a target
   field requires a structural change.

3. Create a new v0.8 YAML document with `library` and `experiments` as its
   top-level sections. Put reusable kinetic or other model elements in the
   library. Put experiment-level optimization settings and dataset-specific
   activations in an experiment. Do not leave v0.7 top-level sections in the
   new document.

4. Convert the model structure field by field. Move constraints to their
   library element, rename `clp_area_penalties` to `clp_penalties`, move
   weights into each affected dataset, and turn each initial-concentration/IRF
   combination into a dataset `activations` mapping. Use the detailed mapping
   and worked patterns in the reference file. Stop and report an ambiguity for
   custom plugins, multiple legacy k-matrices, or explicit unlinked-CLP
   behavior instead of dropping fields.

5. Update Python callers. Replace `load_model` plus `Scheme(model,
   parameters, data)` plus the module-level `optimize` call with
   `load_scheme` and `scheme.optimize(parameters=..., datasets=...)`. Pass
   dataset paths or loaded xarray objects by the exact dataset labels in the
   scheme. Move optimizer options such as maximum function evaluations to the
   `scheme.optimize` call.

6. Validate the port in the target environment. Generate an optional editor
   schema with `create_model_scheme_json_schema`, load the scheme, and run a
   `dry_run=True` optimization before a real fit. Fix unknown fields, missing
   parameters, unresolved element labels, dimension mismatches, and dataset
   name mismatches. For a real migration, compare fitted data and residuals
   first; do not force non-identifiable parameters or decompositions to match.

7. Preserve evidence. Keep the original v0.7 files, the new v0.8 scheme, the
   unchanged-or-justified parameter file, and the updated caller together. In
   the validation workspace use fresh runner outputs and the standard semantic
   comparison procedure; classify documented representation or identifiability
   differences rather than post-processing them away.

## Guardrails

- `Scheme` is no longer the v0.7 container for model, parameters, data, and
  fit options. In v0.8 it represents `library` plus `experiments`; parameters
  and datasets are supplied to `scheme.optimize`.
- v0.8 models are Pydantic models with forbidden extra fields. A YAML file that
  still contains `default_megacomplex`, `k_matrix`, or `initial_concentration`
  at the old locations is not a migrated scheme just because it parses as YAML.
- Parameter YAML is largely compatible in the ported examples. Do not rename
  parameter labels merely to mirror new element names.
- Keep a v0.7 run as the behavioral reference. A successful v0.8 load is only
  schema evidence; it is not numerical parity evidence.
- Use `pyglotaran_extras.compat.convert(result)` only when a legacy plotting or
  analysis consumer requires the compatibility projection. Keep native v0.8
  result access in migrated code.
