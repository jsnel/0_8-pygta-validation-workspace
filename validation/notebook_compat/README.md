# Shared notebook compatibility

Install once into the environment selected by the notebook kernel:

```powershell
python -m pip install -e C:/src/0_8-pygta-validation-workspace/validation/notebook_compat
```

Restart an already running notebook kernel after installing the editable package.

The package uses the environment's existing pyglotaran, pyglotaran-extras,
NumPy, xarray, and pandas installations. It deliberately does not upgrade these
scientific dependencies. The validated versions are recorded in run manifests;
compatibility with future releases is not implied.

```python
from pyglotaran_compat import convert_result, simulate, DataStore, matrix_markdown

# v0.8 ModelScheme, or a v0.7 Model in the reference environment:
data = simulate(model, "dataset", parameters, coordinates)
# Keep native_result for persistence and access to the complete v0.8 result:
plotting_result = convert_result(native_result, model)
```

`convert_result` extends the existing extras converter with the validated
notebook projection: reconstructed fitted data and interval weights, labeled
CLP/matrix views, legacy species order, kinetic rates/lifetimes, spectral shapes,
PFID spectra/phases, and scale metadata. It does not refit or force parameters
and non-identifiable decompositions into numerical agreement. A v0.7 result is
returned unchanged. The semantic comparison loaders under
`validation/compatibility` remain separate: they read persisted evidence rather
than adapting live notebook objects.

`simulate` resolves a named dataset in a v0.8 scheme and passes its library,
parameters, coordinates and simulation options to the native simulator. On
v0.7 it delegates to the original model-based simulator. `DataStore` provides
the small in-memory `import_data`/`load_data` interface needed by the migrated
Project notebooks, including duplicate protection and filesystem paths. It is
not a full replacement for Project's disk-backed registry or optimization API.

The migration tool now emits imports rather than helper implementations.
Existing migrated notebooks can be updated without regenerating their analysis:

```powershell
python -m validation.case_studies.consolidate temp/case-studies
```

This replaces only the five known helper definitions and clears stale execution
outputs. It preserves analysis cells and is idempotent. `inventory.json` records
the 12 source notebooks found, including ignored `temp` files. Historical copies
under `validation/runs` are retained unchanged as evidence. Notebook-specific
plotting functions are analysis code and remain in their notebooks.

The compatibility package is maintained here so it can be reviewed, tested and
installed independently of the ignored case-study checkouts. It can later move
into a released extras package without requiring users to copy implementations.
