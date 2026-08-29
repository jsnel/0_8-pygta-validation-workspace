from __future__ import annotations

from pathlib import Path

import nbformat

from validation.case_studies.compare import result_file
from validation.case_studies.validate_schemas import notebook_pairs


def test_result_file_accepts_both_supported_yaml_suffixes(tmp_path: Path) -> None:
    yaml_path = tmp_path / "result.yaml"
    yaml_path.write_text("success: true\n", encoding="utf-8")

    assert result_file(tmp_path) == yaml_path


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
