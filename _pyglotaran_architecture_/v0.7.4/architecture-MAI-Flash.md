# Architecture Guide

## Table of contents

- [1. Purpose and scope](#1-purpose-and-scope)
- [2. Architectural center of gravity](#2-architectural-center-of-gravity)
- [3. Main execution paths](#3-main-execution-paths)
- [4. Core concepts and boundaries](#4-core-concepts-and-boundaries)
- [5. Extension architecture](#5-extension-architecture)
- [6. Persistence and compatibility](#6-persistence-and-compatibility)
- [7. Repository map](#7-repository-map)
- [8. Change guidance and risks](#8-change-guidance-and-risks)

## 1. Purpose and scope

Pyglotaran is a Python framework for global and target analysis of time-resolved spectroscopy data. Its main job is to turn a declarative model, parameter values, and measured datasets into fitted data, residuals, and optimization diagnostics.

The project is not a general-purpose numerical optimization library. Its responsibility is narrower:

- define a model of kinetic or spectral components,
- bind those components to datasets and parameters,
- evaluate the model through residual construction,
- run an optimization loop over free parameters,
- persist model, scheme, parameter, and result artifacts.

It is intentionally outside the project’s responsibility to provide a user interface, a domain-specific GUI, or a general-purpose data science workflow system. The runtime API is centered on Python objects and file-based specifications rather than a web app or a notebook-centric abstraction.

The clearest evidence is in the public entry points:

- [glotaran/optimization/optimize.py](glotaran/optimization/optimize.py) exposes the core optimization function.
- [glotaran/project/project.py](glotaran/project/project.py) provides a higher-level project workflow that loads model/parameter/data files and runs optimization through the core function.
- [glotaran/model/model.py](glotaran/model/model.py) defines the declarative model object and validation logic.
- [glotaran/project/scheme.py](glotaran/project/scheme.py) holds the executable configuration for one analysis run.
- [glotaran/project/result.py](glotaran/project/result.py) holds the post-optimization state and persisted output.

## 2. Architectural center of gravity

The runtime spine is not a single “convenience class” such as Project. The core runtime spine is the combination of:

- Model: the declarative structure of the analysis problem,
- Scheme: the executable analysis configuration for one run,
- optimize(): the orchestration entry point that turns a Scheme into a Result,
- the optimization providers that build residuals and matrices from the model,
- plugin registration for model components and file I/O.

### What each major object actually does

#### Project

Project is a convenience and persistence layer over a folder of analysis assets. It is not the numerical core. It owns file-system organization, naming, and the project-level registry objects that locate model, parameter, data, and result files. Its main methods create or load those resources and then delegate to the core runtime objects. See [glotaran/project/project.py](glotaran/project/project.py).

Evidence from implementation:

- Project.create/open manage the project folder and project.gta file.
- Project.create_scheme assembles a Scheme from project-managed model, parameter, and data assets.
- Project.optimize constructs a Scheme and calls the core optimization function.
- Project is tested as a folder-oriented workflow helper in [glotaran/project/test/test_project.py](glotaran/project/test/test_project.py).

Conclusion: Project is important for workflow ergonomics and persistence, but it is not the architectural center of the numerical algorithm.

#### Scheme

Scheme is the first real executable boundary. It holds the model, parameters, data, and optimization options for a single analysis run. It is the object that the optimizer consumes. See [glotaran/project/scheme.py](glotaran/project/scheme.py).

Its responsibilities are:

- carry the model instance,
- carry parameter values,
- carry the datasets used by the run,
- expose optimization settings such as tolerances, method, and evaluation limits,
- validate the model/parameters pair.

This is the object that should be changed when the analysis configuration for one run needs to change.

#### Model

Model is the declarative specification of the analysis problem. It is not an executable object in the same sense as Scheme or Optimizer. Instead, it describes the structure of the problem: datasets, dataset groups, megacomplexes, weights, CLP constraints, and relations. See [glotaran/model/model.py](glotaran/model/model.py).

It is responsible for:

- loading model specifications from YAML or other serializers,
- generating parameter labels from its structure,
- collecting issues and validation errors,
- exposing the model structure to the optimization layer.

The distinction is important: a Model tells the system what the problem is. A Scheme tells the system how to solve it for a particular run.

#### optimize()

The function in [glotaran/optimization/optimize.py](glotaran/optimization/optimize.py) is the main runtime entry point for numerical solving. It creates an Optimizer from a Scheme and returns a Result. This is the narrowest public API that actually performs optimization.

The implementation is straightforward, but the important point is that it does not directly manipulate the model. It delegates to the optimizer object, which performs the actual residual-based iterative solve.

#### Plugin registration

Plugin registration is a cross-cutting architectural feature rather than a replacement for the core runtime. It enables extension of:

- megacomplex types,
- data I/O formats,
- project I/O formats.

The registry layer is implemented in [glotaran/plugin_system/base_registry.py](glotaran/plugin_system/base_registry.py) and specialized registries in [glotaran/plugin_system/megacomplex_registration.py](glotaran/plugin_system/megacomplex_registration.py), [glotaran/plugin_system/data_io_registration.py](glotaran/plugin_system/data_io_registration.py), and [glotaran/plugin_system/project_io_registration.py](glotaran/plugin_system/project_io_registration.py).

#### Result objects

Result is the post-optimization state container. It holds the optimized parameter set, the original scheme, optimization metrics, and result datasets. It is a data container and persistence boundary, not the optimizer itself. See [glotaran/project/result.py](glotaran/project/result.py).

## 3. Main execution paths

This section describes the important flows as implemented today.

### 3.1 Construction and loading

The first flow is loading or constructing a project and its artifacts.

1. Project.open or Project.create establishes the project folder and project.gta metadata. See [glotaran/project/project.py](glotaran/project/project.py).
2. The project loads model, parameter, and data files through project registries backed by the plugin system and the YAML-based project I/O plugin. See [glotaran/project/project_model_registry.py](glotaran/project/project_model_registry.py), [glotaran/project/project_parameter_registry.py](glotaran/project/project_parameter_registry.py), and [glotaran/project/project_data_registry.py](glotaran/project/project_data_registry.py).
3. Model loading is handled by the YAML project I/O plugin, which converts a specification into a dynamically generated Model class based on registered megacomplex types. See [glotaran/builtin/io/yml/yml.py](glotaran/builtin/io/yml/yml.py).
4. Scheme loading uses the same plugin layer and file-loading helpers for dataclass-like objects. See [glotaran/project/scheme.py](glotaran/project/scheme.py) and [glotaran/project/dataclass_helpers.py](glotaran/project/dataclass_helpers.py).

The data flow at this boundary is:

- file/specification -> Model/Parameters/Scheme object,
- object ownership stays with the in-memory runtime objects,
- file paths are tracked in the object via source_path fields and registry metadata.

### 3.2 Validation and model composition

Model validation is centralized in [glotaran/model/model.py](glotaran/model/model.py).

The flow is:

- collect model items and their constraints,
- inspect parameters if supplied,
- produce a list of ItemIssue objects,
- render them as Markdown or raise ModelError when requested.

This is a declarative validation path. It checks consistency of the model structure and parameter references, but it does not evaluate residuals or run optimization.

### 3.3 Optimization orchestration

The optimization flow begins with a Scheme and proceeds through several layers.

1. Project.create_scheme or a caller creates a Scheme from a model, parameters, and datasets.
2. optimize() in [glotaran/optimization/optimize.py](glotaran/optimization/optimize.py) constructs an Optimizer.
3. Optimizer initializes one OptimizationGroup per dataset group in the model. See [glotaran/optimization/optimizer.py](glotaran/optimization/optimizer.py).
4. The optimizer calls SciPy least_squares with an objective function that evaluates the penalty vector for each trial parameter vector.
5. Each OptimizationGroup computes penalty contributions from its datasets, then the optimizer assembles the final residual vector.
6. On completion, Optimizer.create_result builds a Result object and stores the optimization state.

Compact control-flow sketch:

```text
input: Scheme
output: Result

optimizer = Optimizer(scheme)
free_parameters, initial_values, bounds = scheme.parameters -> arrays

for each dataset group in scheme.model.get_dataset_groups():
    create OptimizationGroup

least_squares(
    objective = objective_function(parameter_vector),
    bounds = (lower_bounds, upper_bounds)
)

objective_function(parameter_vector):
    set parameter values into shared parameter container
    calculate_penalty()
    return residual_vector

calculate_penalty():
    for each optimization group:
        group.calculate(parameters)
    collect each group's full penalty
    return concatenated penalty vector

create_result():
    build Result from optimizer state, parameter history, and group result data
```

This pseudocode is derived from [glotaran/optimization/optimizer.py](glotaran/optimization/optimizer.py) and [glotaran/optimization/optimization_group.py](glotaran/optimization/optimization_group.py).

### 3.4 Residual construction and matrix generation

The core numerical path is split across a few specialist providers.

- DataProvider prepares each dataset into model/global axes and weights.
- MatrixProvider calculates the model matrix for each dataset and applies constraints and relations.
- EstimationProvider computes the residuals and penalty contributions from matrix and data values.

The data transformed at this boundary is:

- raw dataset values and weights -> flattened arrays and matrix containers,
- model structure and CLP constraints/relations -> reduced matrices,
- matrices and data -> residual vectors for the optimizer.

The implementation is in:

- [glotaran/optimization/data_provider.py](glotaran/optimization/data_provider.py)
- [glotaran/optimization/matrix_provider.py](glotaran/optimization/matrix_provider.py)
- [glotaran/optimization/estimation_provider.py](glotaran/optimization/estimation_provider.py)

A concise pseudocode version of the matrix/residual path is:

```text
input: DatasetGroup, Scheme, Parameters
output: residual vector and result datasets

for each dataset model in group:
    prepare data axes and weights
    build model matrix from megacomplexes
    if dataset has global model:
        build global matrix
    apply scale, weight, constraints, and relations
    produce full matrix for the optimizer

for each dataset model:
    estimate fitted data and residuals from matrix and data
    collect penalties
```

This is the central numerical contract of the repository.

### 3.5 Result creation and persistence

When optimization finishes, Optimizer.create_result assembles the Result object and its datasets. The result object then becomes the input to the project and serializer layers.

The persistence flow is implemented in the YAML project I/O plugin and folder result saver:

- [glotaran/builtin/io/yml/yml.py](glotaran/builtin/io/yml/yml.py) saves model, scheme, parameters, and result artifacts.
- [glotaran/builtin/io/folder/folder_plugin.py](glotaran/builtin/io/folder/folder_plugin.py) saves result data to a folder structure.

The result object includes both the optimization summary and the fitted datasets, which are persisted as NetCDF and YAML/CSV artifacts.

## 4. Core concepts and boundaries

### 4.1 Declarative objects vs executable objects

The repository clearly separates declarative configuration from runtime execution.

Declarative objects:

- Model: the problem definition.
- DatasetModel, DatasetGroupModel: the structure of datasets and grouping.
- Megacomplex subclasses: the building blocks of the model.
- Parameters: parameter definitions and values.
- ClpConstraint, ClpRelation, Weight, IntervalItem: declarative model semantics.

Executable/runtime objects:

- Scheme: analysis configuration for one run.
- Optimizer: orchestration of the numerical solve.
- OptimizationGroup, DataProvider, MatrixProvider, EstimationProvider: runtime helpers that transform the declarative model into numerical residuals.
- Result: container for optimized state and diagnostics.

### 4.2 Domain responsibilities

#### Model layer

The model layer owns the composition of the problem. It answers questions such as:

- which megacomplexes are in the model,
- how datasets are grouped,
- which parameters are referenced,
- which CLP constraints and relations apply.

The central class is Model in [glotaran/model/model.py](glotaran/model/model.py). The public extension point for new model pieces is Megacomplex, implemented in [glotaran/model/megacomplex.py](glotaran/model/megacomplex.py).

#### Optimization layer

The optimization layer owns the numerical evaluation of the model. It does not define the model structure; it consumes it. It transforms model structure, data, and parameters into a residual vector for SciPy.

The key classes are:

- Optimizer in [glotaran/optimization/optimizer.py](glotaran/optimization/optimizer.py)
- OptimizationGroup in [glotaran/optimization/optimization_group.py](glotaran/optimization/optimization_group.py)
- DataProvider, MatrixProvider, EstimationProvider in [glotaran/optimization](glotaran/optimization)

#### I/O layer

The I/O layer is plugin-based and should be treated as a boundary between persisted specifications and in-memory runtime objects. It does not contain model semantics and should not contain numerical optimization logic.

#### Diagnostics and result layer

Result and its related result structures hold optimization diagnostics such as covariance, Jacobian, RMSE, and parameter history. This layer should remain output-oriented. It should not define new fitting logic.

## 5. Extension architecture

The repository is designed for extension through registration and subclassing. The extension contract is mostly explicit and type-driven.

### 5.1 Adding a model component

To add a new model component, create a megacomplex subclass that derives from Megacomplex and register it with the megacomplex decorator.

Relevant files:

- [glotaran/model/megacomplex.py](glotaran/model/megacomplex.py)
- [glotaran/plugin_system/megacomplex_registration.py](glotaran/plugin_system/megacomplex_registration.py)
- [glotaran/model/model.py](glotaran/model/model.py)

Minimal change:

1. Implement a subclass of Megacomplex.
2. Implement calculate_matrix and, if needed, finalize_data.
3. Register it with the megacomplex decorator so the model loader can resolve the type from YAML.
4. Add tests that validate the new component is discoverable and that a model containing it can be created and optimized.

### 5.2 Adding a residual or optimization algorithm

The optimizer entry point is a single place to change if the project needs a different optimization backend or a different objective handling strategy.

Relevant files:

- [glotaran/optimization/optimize.py](glotaran/optimization/optimize.py)
- [glotaran/optimization/optimizer.py](glotaran/optimization/optimizer.py)
- [glotaran/optimization/optimization_group.py](glotaran/optimization/optimization_group.py)

Minimal change:

1. Extend the optimizer or add a new algorithm-specific wrapper around the current objective contract.
2. Keep the public contract stable: objective_function should return a residual/penalty vector, and create_result should produce a Result.
3. Add tests around parameter history, result fields, and failure handling.

### 5.3 Adding a file format or serializer

The serializer boundary is plugin-based. New formats should implement ProjectIoInterface and be registered with the project I/O decorator.

Relevant files:

- [glotaran/io/interface.py](glotaran/io/interface.py)
- [glotaran/plugin_system/project_io_registration.py](glotaran/plugin_system/project_io_registration.py)
- [glotaran/builtin/io/yml/yml.py](glotaran/builtin/io/yml/yml.py)
- [glotaran/plugin_system/test/test_project_io_registration.py](glotaran/plugin_system/test/test_project_io_registration.py)

Minimal change:

1. Implement load_model/save_model and related methods for Parameters, Scheme, and Result if the format should be a full project format.
2. Register the plugin with the project IO decorator.
3. Add tests that verify registration and round-trip loading/saving.

### 5.4 Adding a result diagnostic

Diagnostic fields are stored on Result and populated by Optimizer.create_result. A new diagnostic usually belongs in the result object and the optimizer’s result-construction path.

Relevant files:

- [glotaran/project/result.py](glotaran/project/result.py)
- [glotaran/optimization/optimizer.py](glotaran/optimization/optimizer.py)

Minimal change:

1. Add a field to Result.
2. Populate it in Optimizer.create_result.
3. Make sure the serializer can persist it if it is part of the persisted contract.
4. Add tests that validate both populated and missing values.

### 5.5 Adding a preprocessing step

Preprocessing is currently a boundary concern rather than a first-class extension framework. The main place to hook it in is the project workflow before creating the Scheme, or the Scheme/data-loading path, depending on whether it is project-level or analysis-level.

Relevant files:

- [glotaran/project/project.py](glotaran/project/project.py)
- [glotaran/optimization/optimizer.py](glotaran/optimization/optimizer.py)

Minimal change:

1. Decide whether the preprocessing step should be part of data import or part of the optimization setup.
2. Apply it before the data is handed to DataProvider.
3. Keep the data contract stable: the optimization path expects datasets with the expected coordinates and dimensions.

### 5.6 Adding a high-level workflow helper

High-level helpers belong at the Project layer or in a thin wrapper module. They should not contain numerical optimization logic.

Relevant files:

- [glotaran/project/project.py](glotaran/project/project.py)

Minimal change:

1. Add a method on Project that composes existing project and core functions.
2. Leave the numerical algorithm to optimize() and the optimizer layer.
3. Add tests that cover the public workflow and the file-system side effects.

## 6. Persistence and compatibility

### 6.1 Supported formats

The project supports several data and project file formats through plugins.

Data I/O:

- NetCDF via [glotaran/builtin/io/netCDF/netCDF.py](glotaran/builtin/io/netCDF/netCDF.py)
- ASCII via [glotaran/builtin/io/ascii/wavelength_time_explicit_file.py](glotaran/builtin/io/ascii/wavelength_time_explicit_file.py)
- SDT via [glotaran/builtin/io/sdt/sdt_file_reader.py](glotaran/builtin/io/sdt/sdt_file_reader.py)

Project I/O:

- YAML via [glotaran/builtin/io/yml/yml.py](glotaran/builtin/io/yml/yml.py)
- folder-based result persistence via [glotaran/builtin/io/folder/folder_plugin.py](glotaran/builtin/io/folder/folder_plugin.py)

### 6.2 Schema and versioning behavior

The persistence layer is file-based and uses the version in the project.gta header as a basic compatibility marker. See [glotaran/project/project.py](glotaran/project/project.py). The result and scheme objects also carry source_path and loader references for deserialization.

The current code uses the installed pyglotaran package version as the project version. That means compatibility is partly tied to the library version used to write the files. The repository’s tests explicitly check that Project.open uses the version from the project file and overwrites the runtime version when different. See [glotaran/project/test/test_project.py](glotaran/project/test/test_project.py).

### 6.3 Runtime state vs persisted state

Runtime state and persisted state are not identical.

- Runtime objects contain live Python objects, such as Model, Parameters, and Result with in-memory arrays and history.
- Persisted state is a serialized representation of those objects, often split across YAML, CSV, and NetCDF files.
- Result data is persisted in a way that includes fitted data, residuals, matrices, and CLP arrays as datasets.

The serializer must therefore be treated as a lossy or transform-oriented boundary. The runtime object is richer than the serialized form, and the serializer may convert, filter, or rename fields.

## 7. Repository map

The architectural packages are:

- [glotaran/model](glotaran/model): declarative model structure, validation, and extension points for megacomplexes and model items.
- [glotaran/optimization](glotaran/optimization): numerical evaluation, optimization orchestration, data/matrix/estimation providers, and result generation.
- [glotaran/parameter](glotaran/parameter): parameter definitions, bounds, history, and parameter mutation logic.
- [glotaran/project](glotaran/project): project folders, Scheme, Result, and folder-level workflow logic.
- [glotaran/io](glotaran/io): plugin-facing I/O API and shared interfaces.
- [glotaran/plugin_system](glotaran/plugin_system): registry and plugin discovery infrastructure.
- [glotaran/builtin/io](glotaran/builtin/io): built-in serializer and data I/O implementations.
- [glotaran/testing](glotaran/testing): test utilities and plugin-system stubs.

The most important files to know when changing behavior are:

- [glotaran/optimization/optimizer.py](glotaran/optimization/optimizer.py)
- [glotaran/optimization/optimization_group.py](glotaran/optimization/optimization_group.py)
- [glotaran/model/model.py](glotaran/model/model.py)
- [glotaran/project/project.py](glotaran/project/project.py)
- [glotaran/project/scheme.py](glotaran/project/scheme.py)
- [glotaran/project/result.py](glotaran/project/result.py)
- [glotaran/builtin/io/yml/yml.py](glotaran/builtin/io/yml/yml.py)
- [glotaran/plugin_system/base_registry.py](glotaran/plugin_system/base_registry.py)

## 8. Change guidance and risks

### Where to place new behavior

- Put new model semantics into the model layer, typically as a new megacomplex or a new model item type.
- Put new numerical behavior into the optimization layer, especially Optimizer, OptimizationGroup, DataProvider, MatrixProvider, or EstimationProvider.
- Put new file-format behavior into the I/O plugin layer.
- Put workflow helpers into Project or another thin wrapper layer.
- Put result diagnostics into Result and the optimizer’s result-construction path.

### Layers that should not depend on each other directly

Avoid letting the I/O layer contain optimization logic or letting the optimization layer define new model schema without going through the model layer. A useful rule of thumb is:

- the model layer should not depend on serializer details,
- the optimization layer should not depend on project-folder conventions,
- the project layer should not embed numerical algorithm details.

### Stable abstractions

The following contracts are relatively stable and should not be changed casually:

- the Model -> Scheme -> optimize() -> Result flow,
- the Megacomplex.calculate_matrix contract,
- the optimizer’s objective function contract (a residual/penalty vector),
- the plugin registration interfaces in the I/O and megacomplex registries.

### Risky refactors and hidden coupling

The main risks are:

- mutating shared parameter state during optimization,
- changing the shape or meaning of the penalty/residual vector without updating the optimizer and tests,
- changing the dataset/matrix contract between DataProvider and EstimationProvider,
- changing plugin registration order or registry behavior in ways that affect discovery,
- changing serializer behavior without preserving the expected round-trip semantics.

### Plugin-ordering and compatibility concerns

Because plugins are registered globally and then resolved by name, plugin ordering and overriding behavior matter. The registry layer warns on overwrite attempts and exposes explicit override helpers. See [glotaran/plugin_system/base_registry.py](glotaran/plugin_system/base_registry.py) and the tests in [glotaran/plugin_system/test/test_data_io_registration.py](glotaran/plugin_system/test/test_data_io_registration.py).

### Testing expectations

Most important changes should be covered by tests in the relevant package area:

- model behavior: [glotaran/model](glotaran/model)
- optimization behavior: [glotaran/optimization](glotaran/optimization)
- project workflow: [glotaran/project/test/test_project.py](glotaran/project/test/test_project.py)
- plugin system: [glotaran/plugin_system/test](glotaran/plugin_system/test)

### Before changing X, inspect Y

- Before changing the optimization contract, inspect [glotaran/optimization/optimizer.py](glotaran/optimization/optimizer.py) and [glotaran/optimization/optimization_group.py](glotaran/optimization/optimization_group.py).
- Before changing model composition, inspect [glotaran/model/model.py](glotaran/model/model.py) and [glotaran/model/megacomplex.py](glotaran/model/megacomplex.py).
- Before changing persistence, inspect [glotaran/builtin/io/yml/yml.py](glotaran/builtin/io/yml/yml.py) and [glotaran/io/interface.py](glotaran/io/interface.py).
- Before changing project workflow behavior, inspect [glotaran/project/project.py](glotaran/project/project.py).
- Before changing plugin behavior, inspect [glotaran/plugin_system/base_registry.py](glotaran/plugin_system/base_registry.py).

## Notes on what is inferred vs directly established

Most of the guidance above is directly based on implementation in the repository. The main inferred conclusion is the architectural emphasis: the project is centered on the Model -> Scheme -> optimize() -> Result flow, while Project and plugin registration primarily provide workflow and extensibility infrastructure around that core. That conclusion is supported by the implementation and tests, but it is still an architectural interpretation of the code rather than a literal single class name or entry point.
