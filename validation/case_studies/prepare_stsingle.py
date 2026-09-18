"""Prepare the ST-single v0.8 staging notebook and translated model.

The ST model uses legacy ``global_megacomplex`` dataset fields, which the
generic case-study migrator intentionally does not infer.  This adapter keeps
those fields explicit as v0.8 ``global_elements`` and preserves their scales.
"""

from __future__ import annotations

import argparse
import ast
import copy
from pathlib import Path
from typing import Any

import nbformat
import yaml

from validation.case_studies.migrate import (
    HELPERS,
    NotebookMigrator,
    convert_model,
    migrated_path,
    schema_documents,
)


NOTEBOOK_NAME = "20260915STsingle_State1_2_6comp_per_day2Olli_shifted.ipynb"
MODEL_NAME = "20260915STsingle_State1_2_6comp_day1_Olli.yml"
STAGING_NOTE = (
    "# v0.8 staging execution\n\n"
    "Run this notebook with `temp/pyglotaran-staging-dev/.venv-stsingle/Scripts/python.exe`. "
    "This isolated staging environment uses SciPy 1.15.3, required for the "
    "rank-deficient NNLS case; the locked staging SciPy 1.14.1 fails in its "
    "normal-equation solve. The scientific model and NNLS residual semantics "
    "are unchanged."
)


def _translate_model(source: Path, destination: Path) -> None:
    document = schema_documents(source.parent.parent)[source]
    document = copy.deepcopy(document)
    globals_by_dataset: dict[str, tuple[Any, Any]] = {}
    for label, item in (document.get("dataset") or {}).items():
        globals_by_dataset[label] = (
            item.pop("global_megacomplex", None),
            item.pop("global_megacomplex_scale", None),
        )
    converted, _ = convert_model(document, source, clp_link_tolerance=None)
    for experiment in converted["experiments"].values():
        for label, dataset in experiment["datasets"].items():
            elements, scales = globals_by_dataset.get(label, (None, None))
            if elements:
                dataset["global_elements"] = elements
                # Global-result reconstruction reads the dataset solver, while
                # optimization reads the experiment solver. Preserve NNLS in both.
                dataset["residual_function"] = experiment["residual_function"]
            if scales:
                dataset["global_element_scale"] = dict(
                    zip(elements, scales, strict=True)
                )
    converted["experiments"] = {
        label: experiment
        for label, experiment in converted["experiments"].items()
        if experiment.get("datasets")
    }
    destination.write_text(
        "# Migrated from pyglotaran v0.7 for v0.8 staging validation.\n"
        + yaml.safe_dump(converted, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _translate_notebook(
    source: Path, destination: Path, model_documents: dict[Path, dict[str, Any]]
) -> None:
    notebook = nbformat.read(source, as_version=4)
    note = nbformat.v4.new_markdown_cell(STAGING_NOTE)
    note["id"] = "stsingle-runtime"
    notebook.cells.insert(0, note)
    migrator = NotebookMigrator(destination.parent.resolve(), model_documents)
    first_code_cell = True
    for cell in notebook.cells:
        if cell.cell_type != "code":
            continue
        old_access = migrator.replace_old_model_access(cell.source)
        if old_access is not None:
            cell.source = old_access
        else:
            tree = ast.parse(cell.source or "pass")
            migrated = migrator.visit(tree)
            ast.fix_missing_locations(migrated)
            cell.source = ast.unparse(migrated)
        cell.source = _rewrite_native_result_save(cell.source)
        if "model.validate(parameters=parameters)" in cell.source:
            cell.source = cell.source.replace(
                "print(model.validate(parameters=parameters))",
                "print('Model scheme loaded; parameter validation is performed by the v0.8 optimizer.')",
            )
        if first_code_cell:
            cell.source = f"{HELPERS}\n\n{cell.source}"
            first_code_cell = False
        cell.outputs = []
        cell.execution_count = None
    nbformat.write(notebook, destination)


def _rewrite_native_result_save(source: str) -> str:
    """Save native results in a unique directory beside supplied artifacts."""

    tree = ast.parse(source or "pass")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "save" or not isinstance(node.func.value, ast.Name):
            continue
        if node.func.value.id != "result" or len(node.args) != 1:
            continue
        replacement = ast.parse(
            """
from datetime import datetime, timezone
from pathlib import Path
from tempfile import mkdtemp

_native_result_root = Path("results")
_native_result_root.mkdir(parents=True, exist_ok=True)
_native_result_dir = Path(
    mkdtemp(
        prefix=(
            "20260915STsingle_State1_2_native_"
            f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S.%fZ}_"
        ),
        dir=_native_result_root,
    )
)
result_native.save(_native_result_dir / "result.yml")
            """
        ).body
        parent = next(
            (
                candidate
                for candidate in ast.walk(tree)
                if isinstance(candidate, ast.Expr) and candidate.value is node
            ),
            None,
        )
        if parent is None:
            continue
        for candidate in ast.walk(tree):
            if isinstance(candidate, ast.Module):
                for index, statement in enumerate(candidate.body):
                    if statement is parent:
                        candidate.body[index : index + 1] = replacement
                        ast.fix_missing_locations(tree)
                        return ast.unparse(tree)
    return source


def prepare(reference_root: Path, staging_root: Path) -> dict[str, str]:
    """Generate the ST staging model and notebook from the reference inputs."""
    reference_root = reference_root.resolve()
    staging_root = staging_root.resolve()
    source_model = reference_root / "models" / MODEL_NAME
    source_notebook = reference_root / NOTEBOOK_NAME
    staging_model = staging_root / "models" / migrated_path(Path(MODEL_NAME)).name
    staging_notebook = staging_root / NOTEBOOK_NAME
    staging_model.parent.mkdir(parents=True, exist_ok=True)

    _translate_model(source_model, staging_model)
    reference_documents = schema_documents(reference_root)
    # Notebook model expressions resolve the legacy staging-relative path
    # first; the migrator then rewrites that path to the generated ``_v08``
    # model.  Keep the document keyed by the legacy path for that lookup.
    staging_source_model = staging_root / "models" / MODEL_NAME
    staging_documents = {staging_source_model: reference_documents[source_model]}
    _translate_notebook(source_notebook, staging_notebook, staging_documents)
    return {"model": str(staging_model), "notebook": str(staging_notebook)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--staging-root", type=Path, required=True)
    args = parser.parse_args()
    print(prepare(args.reference_root, args.staging_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
