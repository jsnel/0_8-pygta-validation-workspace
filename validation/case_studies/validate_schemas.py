"""Generate parameter-aware schemas and strictly load migrated case-study schemes."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import nbformat

from glotaran.io import load_scheme
from glotaran.utils.json_schema import create_model_scheme_json_schema


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def constant_call(node: ast.AST, function: str, constants: dict[str, str]) -> str | None:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return None
    if node.func.id != function or not node.args:
        return None
    argument = node.args[0]
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
        return argument.value
    if isinstance(argument, ast.Name):
        return constants.get(argument.id)
    return None


def notebook_pairs(root: Path) -> dict[Path, Path | None]:
    pairs: dict[Path, Path | None] = {}
    for notebook_path in sorted(root.rglob("*_v08.ipynb")):
        notebook = nbformat.read(notebook_path, as_version=4)
        constants: dict[str, str] = {}
        parameter_variables: dict[str, Path] = {}
        scheme_variables: dict[str, Path] = {}
        for cell in notebook.cells:
            if cell.cell_type != "code":
                continue
            tree = ast.parse(cell.source or "pass")
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
                if not targets:
                    continue
                target = targets[0]
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    constants[target] = node.value.value
                parameter = constant_call(node.value, "load_parameters", constants)
                if parameter:
                    parameter_variables[target] = (notebook_path.parent / parameter).resolve()
                model = constant_call(node.value, "load_scheme", constants)
                if model:
                    model_path = (notebook_path.parent / model).resolve()
                    scheme_variables[target] = model_path
                    pairs.setdefault(model_path, None)
                if target.endswith("_parameters") and isinstance(node.value, ast.Name):
                    scheme = target.removesuffix("_parameters")
                    model_path = scheme_variables.get(scheme)
                    parameter_path = parameter_variables.get(node.value.id)
                    if model_path is not None and parameter_path is not None:
                        pairs[model_path] = parameter_path
                elif target.endswith("_parameters") and parameter:
                    scheme = target.removesuffix("_parameters")
                    model_path = scheme_variables.get(scheme)
                    if model_path is not None:
                        pairs[model_path] = parameter_variables[target]
    return pairs


def validate(root: Path, output: Path, slug: str) -> dict[str, Any]:
    records = []
    schema_root = output.parent / "schemas"
    for model, parameters in sorted(notebook_pairs(root).items()):
        relative = model.relative_to(root)
        schema_path = schema_root / relative.with_suffix(".schema.json")
        record: dict[str, Any] = {
            "model": str(model),
            "model_sha256": sha256(model),
            "parameters": str(parameters) if parameters else None,
            "parameters_sha256": sha256(parameters) if parameters and parameters.is_file() else None,
            "schema": str(schema_path),
        }
        try:
            create_model_scheme_json_schema(schema_path, parameters=parameters)
            load_scheme(model)
            record.update(
                {
                    "parameter_aware_schema": "PASS" if parameters else "NOT_PRACTICAL",
                    "load": "PASS",
                    "schema_sha256": sha256(schema_path),
                }
            )
        except Exception as error:  # noqa: BLE001 - package exact validation failure
            record.update({"parameter_aware_schema": "FAIL", "load": "FAIL", "error": repr(error)})
        records.append(record)
    return {
        "version": 1,
        "slug": slug,
        "staging_root": str(root),
        "scheme_count": len(records),
        "all_passed": bool(records) and all(record["load"] == "PASS" for record in records),
        "schemes": records,
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Migrated scheme validation: {report['slug']}",
        "",
        f"Schemes: **{report['scheme_count']}**; schema/load pass: **{report['all_passed']}**.",
        "",
        "| Scheme | Parameter-aware schema | Strict load |",
        "|---|---|---|",
    ]
    for record in report["schemes"]:
        lines.append(
            f"| {Path(record['model']).name} | {record['parameter_aware_schema']} | {record['load']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate(args.root.resolve(), args.output.resolve(), args.slug)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    args.output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
