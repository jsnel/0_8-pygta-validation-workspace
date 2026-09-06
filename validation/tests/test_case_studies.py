from __future__ import annotations

from pathlib import Path

import nbformat

from validation.case_studies.compare import compare
from validation.case_studies.compare import result_file
from validation.case_studies.compare import result_roots
from validation.case_studies.migrate import convert_model
from validation.case_studies.migrate import migrate_notebook
from validation.case_studies.migrate import notebook_clp_link_tolerances
from validation.case_studies.run_case_study import environment_metadata
from validation.case_studies.run_case_study import instrument_fit_results
from validation.case_studies.run_case_study import source_patch
from validation.case_studies.validate_schemas import notebook_pairs


def test_result_file_accepts_both_supported_yaml_suffixes(tmp_path: Path) -> None:
    yaml_path = tmp_path / "result.yaml"
    yaml_path.write_text("success: true\n", encoding="utf-8")

    assert result_file(tmp_path) == yaml_path


def test_result_roots_prefers_instrumented_captures(tmp_path: Path) -> None:
    captured = tmp_path / "case-study-results" / "fit-001"
    incidental = tmp_path / "results" / "run-0001"
    captured.mkdir(parents=True)
    incidental.mkdir(parents=True)
    (captured / "result.yaml").write_text("success: true\n", encoding="utf-8")
    (incidental / "result.yaml").write_text("success: true\n", encoding="utf-8")

    assert result_roots(tmp_path) == {"fit-001": captured}


def test_notebook_pairs_resolves_variable_model_and_parameter_paths(tmp_path: Path) -> None:
    notebook_path = tmp_path / "analysis_v08.ipynb"
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_code_cell(
                "\n".join(
                    [
                        "model_path = 'models/example_v08.yml'",
                        "parameter_path = 'models/example.csv'",
                        "parameters = load_parameters(parameter_path)",
                        "scheme = load_scheme(model_path)",
                        "scheme_parameters = parameters",
                    ]
                )
            )
        ]
    )
    nbformat.write(notebook, notebook_path)

    pairs = notebook_pairs(tmp_path)

    assert pairs == {
        (tmp_path / "models/example_v08.yml").resolve(): (
            tmp_path / "models/example.csv"
        ).resolve()
    }


def test_convert_model_translates_legacy_coherent_artifact_constraint_label(
    tmp_path: Path,
) -> None:
    document = {
        "dataset_groups": {"default": {"link_clp": True}},
        "dataset": {
            "dataset1": {
                "group": "default",
                "megacomplex": ["artifact"],
                "initial_concentration": "input",
                "irf": "irf",
            }
        },
        "megacomplex": {"artifact": {"type": "coherent-artifact", "order": 1}},
        "initial_concentration": {"input": {"compartments": [], "parameters": []}},
        "irf": {"irf": {"type": "gaussian", "center": "irf.center", "width": "irf.width"}},
        "clp_constraints": [
            {"type": "zero", "target": "coherent_artifact_1_artifact", "interval": [[1, 2]]}
        ],
    }

    converted, log = convert_model(document, tmp_path / "model.yml")

    constraint = converted["library"]["artifact"]["clp_constraints"][0]
    assert constraint["target"] == "artifact_derivative_0"
    assert log["clp_label_translations"] == [
        {
            "legacy": "coherent_artifact_1_artifact",
            "migrated": "artifact_derivative_0",
            "element": "artifact",
        }
    ]


def test_convert_model_excludes_non_kinetic_amplitudes_from_normalization(
    tmp_path: Path,
) -> None:
    document = {
        "dataset": {
            "dataset1": {
                "megacomplex": ["decay", "artifact", "doas"],
                "initial_concentration": "input",
                "irf": "irf",
            }
        },
        "megacomplex": {
            "decay": {"type": "decay", "k_matrix": ["km"]},
            "artifact": {"type": "coherent-artifact", "order": 1},
            "doas": {
                "type": "damped-oscillation",
                "labels": ["osc1"],
                "frequencies": ["osc.freq.1"],
                "rates": ["osc.rate.1"],
            },
        },
        "k_matrix": {"km": {"matrix": {"(s1, s1)": "rates.k1"}}},
        "initial_concentration": {
            "input": {"compartments": ["s1"], "parameters": ["input.s1"]}
        },
        "irf": {"irf": {"type": "gaussian", "center": "irf.center", "width": "irf.width"}},
    }

    converted, _ = convert_model(document, tmp_path / "model.yml")

    activation = converted["experiments"]["default"]["datasets"]["dataset1"]["activations"]["irf"]
    # The v0.8 coherent-artifact and damped-oscillation elements require their amplitudes
    # in the activation, but v0.7 never counted them in the initial-concentration
    # normalization sum, so they must not count towards it here either.
    assert activation["compartments"] == {"s1": "input.s1", "artifact": 1, "osc1": 1}
    assert activation["not_normalized_compartments"] == ["artifact", "osc1"]


def test_convert_model_maps_pfid_and_preserves_unlinked_clps(tmp_path: Path) -> None:
    document = {
        "dataset_groups": {
            "default": {"residual_function": "variable_projection", "link_clp": False}
        },
        "dataset": {
            "stokes": {
                "megacomplex": ["pfid", "decay"],
                "initial_concentration": "input",
                "irf": "irf",
            },
            "anti_stokes": {
                "megacomplex": ["pfid", "decay"],
                "initial_concentration": "input",
                "irf": "irf",
            },
        },
        "megacomplex": {
            "pfid": {
                "type": "pfid",
                "labels": ["osc1"],
                "frequencies": ["osc.frequency"],
                "rates": ["osc.rate"],
            },
            "decay": {"type": "decay", "k_matrix": ["km"]},
        },
        "k_matrix": {"km": {"matrix": {"(s1, s1)": "rates.k1"}}},
        "initial_concentration": {
            "input": {"compartments": ["s1"], "parameters": ["input.s1"]}
        },
        "irf": {
            "irf": {
                "type": "spectral-gaussian",
                "center": "irf.center",
                "width": "irf.width",
            }
        },
    }

    converted, log = convert_model(document, tmp_path / "model.yml")

    assert converted["library"]["pfid"] == {
        "type": "pfid",
        "oscillations": {
            "osc1": {"frequency": "osc.frequency", "rate": "osc.rate"}
        },
    }
    assert set(converted["experiments"]) == {
        "default__stokes",
        "default__anti_stokes",
    }
    stokes = converted["experiments"]["default__stokes"]["datasets"]["stokes"]
    assert stokes["activation"]["type"] == "multi-gaussian"
    assert stokes["activation"]["center"] == ["irf.center"]
    assert stokes["activation"]["width"] == ["irf.width"]
    assert stokes["activations"]["irf"]["type"] == "gaussian"
    assert len(log["unlinked_clp_splits"]) == 2


def test_convert_model_allows_irf_only_nonkinetic_dataset(tmp_path: Path) -> None:
    document = {
        "dataset": {
            "artifact_data": {
                "megacomplex": ["artifact", "doas"],
                "irf": "irf",
            }
        },
        "megacomplex": {
            "artifact": {"type": "coherent-artifact", "order": 1},
            "doas": {
                "type": "damped-oscillation",
                "labels": ["osc1"],
                "frequencies": ["osc.frequency"],
                "rates": ["osc.rate"],
            },
        },
        "irf": {
            "irf": {
                "type": "spectral-gaussian",
                "center": "irf.center",
                "width": "irf.width",
            }
        },
    }

    converted, _ = convert_model(document, tmp_path / "model.yml")

    activation = converted["experiments"]["default"]["datasets"][
        "artifact_data"
    ]["activations"]["irf"]
    assert activation["compartments"] == {"artifact": 1, "osc1": 1}
    assert activation["not_normalized_compartments"] == ["artifact", "osc1"]


def test_convert_model_records_inert_weight_dataset_selectors(tmp_path: Path) -> None:
    document = {
        "dataset": {"dataset1": {"megacomplex": ["kinetic"]}},
        "megacomplex": {"kinetic": {"type": "clp-guide", "target": "s1"}},
        "weights": [{"datasets": ["disabled_dataset"], "value": 2}],
    }

    converted, log = convert_model(document, tmp_path / "model.yml")

    assert "weights" not in converted["experiments"]["default"]["datasets"]["dataset1"]
    assert log["inert_weight_dataset_selectors"][0]["dataset"] == "disabled_dataset"


def test_convert_model_records_relation_between_inactive_elements(tmp_path: Path) -> None:
    document = {
        "dataset": {"dataset1": {"megacomplex": ["active"]}},
        "megacomplex": {
            "active": {"type": "clp-guide", "target": "active"},
            "inactive1": {"type": "clp-guide", "target": "inactive1"},
            "inactive2": {"type": "clp-guide", "target": "inactive2"},
        },
        "clp_relations": [
            {"source": "inactive1", "target": "inactive2", "parameter": "relation.1"}
        ],
    }

    converted, log = convert_model(document, tmp_path / "model.yml")

    assert "clp_relations" not in converted["experiments"]["default"]
    assert log["inert_relations_and_penalties"][0]["source"] == "inactive1"


def test_migrate_notebook_loads_parameter_path_variable(tmp_path: Path) -> None:
    model_path = tmp_path / "models" / "model.yml"
    notebook_path = tmp_path / "analysis.ipynb"
    notebook_path.parent.mkdir(parents=True, exist_ok=True)
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_code_cell(
                "\n".join(
                    [
                        "model_path = 'models/model.yml'",
                        "parameter_path = 'models/parameters.csv'",
                        "scheme = Scheme(model=model_path, parameters=parameter_path, data={'dataset': 'data.ascii'})",
                        "simulated = simulate(load_model(model_path), 'dataset', load_parameters(parameter_path), coordinates)",
                    ]
                )
            )
        ]
    )
    nbformat.write(notebook, notebook_path)

    migrated = migrate_notebook(path=notebook_path, model_documents={model_path: {}})
    code = "\n".join(
        cell.source for cell in nbformat.read(migrated, as_version=4).cells if cell.cell_type == "code"
    )

    assert "scheme_parameters = load_parameters(parameter_path)" in code
    assert "_case_study_simulate(load_scheme(model_path), 'dataset'" in code


def test_migrate_notebook_converts_project_optimize(tmp_path: Path) -> None:
    model_path = tmp_path / "models" / "model.yml"
    model_path.parent.mkdir(parents=True)
    notebook_path = tmp_path / "analysis.ipynb"
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_code_cell(
                "\n".join(
                    [
                        "from glotaran.project import Project",
                        "SAVING_OPTIONS_DEFAULT.data_filter = []",
                        "project = Project.open('')",
                        "result = project.optimize(",
                        "    model_name='model',",
                        "    parameters_name='parameters',",
                        "    data_lookup_override={'dataset': data},",
                        "    maximum_number_function_evaluations=1,",
                        ")",
                    ]
                )
            )
        ]
    )
    nbformat.write(notebook, notebook_path)

    migrated = migrate_notebook(
        path=notebook_path, model_documents={model_path: {}}
    )
    code = "\n".join(
        cell.source
        for cell in nbformat.read(migrated, as_version=4).cells
        if cell.cell_type == "code"
    )

    assert "from glotaran.project import Project" not in code
    assert "project = _CaseStudyDataStore()" in code
    assert "SAVING_OPTIONS_DEFAULT['data_filter'] = []" in code
    assert "result_scheme = load_scheme('models/model_v08.yml')" in code
    assert "result_scheme_parameters = load_parameters('parameters/parameters.csv')" in code
    assert "result_scheme_dry_run = result_scheme.optimize" in code
    assert "result_native = result_scheme.optimize" in code


def test_notebook_clp_link_tolerance_is_associated_with_model(tmp_path: Path) -> None:
    model_path = tmp_path / "models" / "example.yml"
    model_path.parent.mkdir()
    model_path.write_text("dataset: {}\nmegacomplex: {}\n", encoding="utf-8")
    notebook_path = tmp_path / "analysis.ipynb"
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_code_cell(
                "scheme = Scheme(model='models/example.yml', parameters='parameters.csv', "
                "data={}, clp_link_tolerance=2.1)"
            )
        ]
    )
    nbformat.write(notebook, notebook_path)

    tolerances = notebook_clp_link_tolerances([notebook_path], {model_path: {}})

    assert tolerances == {model_path.resolve(): 2.1}


def test_fit_captures_do_not_overwrite_between_notebooks() -> None:
    paths = []
    for name in ("step_1", "step_2"):
        notebook = nbformat.v4.new_notebook(cells=[
            nbformat.v4.new_code_cell("result = optimize(scheme)")
        ])
        captures = instrument_fit_results(notebook, namespace=name)
        paths.append(captures[0]["result_path"])
        assert captures[0]["result_path"] in notebook.cells[1].source
    assert len(set(paths)) == 2


def test_instrument_fit_results_skips_dry_runs() -> None:
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_code_cell(
                "dry = scheme.optimize(dry_run=True)\nresult_native = scheme.optimize(parameters=p, datasets=d)"
            )
        ]
    )

    captures = instrument_fit_results(notebook)

    assert captures == [
        {
            "variable": "result_native",
            "result_path": "case-study-results/fit-001-result/result.yaml",
        }
    ]
    assert "result=result_native" in notebook.cells[1].source
    assert "result=dry" not in notebook.cells[1].source
    assert "saving_options=_case_study_capture_saving_options" in notebook.cells[1].source


def test_environment_metadata_is_populated() -> None:
    metadata = environment_metadata()

    assert metadata["python_executable"]
    assert metadata["platform"]
    assert isinstance(metadata["pip_freeze"], list)


def test_compare_reports_missing_artifact_for_empty_roots(tmp_path: Path) -> None:
    reference = tmp_path / "reference"
    staging = tmp_path / "staging"
    reference.mkdir()
    staging.mkdir()

    report = compare(reference, staging, "empty")

    assert report["summary"]["provisional_status"] == "MISSING_ARTIFACT"
    assert report["summary"]["status_counts"]["MISSING_ARTIFACT"] == 1


def test_source_patch_includes_untracked_files(tmp_path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            "base",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    untracked = tmp_path / "migration.yml"
    untracked.write_text("library: {}\n", encoding="utf-8")

    patch = source_patch(tmp_path, "HEAD")

    assert "migration.yml" in patch
    assert "library: {}" in patch
