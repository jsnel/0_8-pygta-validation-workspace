"""Create provisional semantic comparisons for external case-study results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compatibility.metrics import compare_arrays  # noqa: E402
from compatibility.normalize import canonicalize_array  # noqa: E402
from compatibility.normalize import first_data_array  # noqa: E402


FIT_TOLERANCE = 1e-6
ARRAY_RTOL = 1e-5
ARRAY_ATOL = 1e-8
PARAMETER_RTOL = 1e-4
PARAMETER_ATOL = 1e-8


def result_file(root: Path) -> Path | None:
    return next((root / name for name in ("result.yml", "result.yaml") if (root / name).is_file()), None)


def document(root: Path) -> tuple[Path, dict[str, Any]]:
    path = result_file(root)
    if path is None:
        raise FileNotFoundError(f"No result.yml or result.yaml in {root}")
    return path, yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def result_roots(root: Path) -> dict[str, Path]:
    leaves: dict[str, Path] = {}
    for name in ("result.yml", "result.yaml"):
        for path in root.rglob(name):
            leaves[path.parent.relative_to(root).as_posix()] = path.parent
    return leaves


def array_from_file(path: Path, preferred: str | None = None) -> xr.DataArray:
    dataset = xr.load_dataset(path)
    array = first_data_array(dataset, preferred)
    return canonicalize_array(array)[0]


def load_v07(root: Path) -> dict[str, Any]:
    path, doc = document(root)
    datasets: dict[str, Any] = {}
    aliases = {
        "data": "data",
        "residual": "residual",
        "fitted_data": "fitted_data",
        "clp": "clp",
        "matrix": "matrix",
        "weight": "weight",
        "weighted_residual": "weighted_residual",
    }
    for label, relative in (doc.get("data") or {}).items():
        source = root / relative
        raw = xr.load_dataset(source)
        variables = {
            aliases[name]: canonicalize_array(value)[0]
            for name, value in raw.data_vars.items()
            if name in aliases
        }
        datasets[label] = {
            "variables": variables,
            "metadata": dict(raw.attrs),
            "source_files": [str(source)],
        }
    parameter_path = root / doc["optimized_parameters"] if doc.get("optimized_parameters") else None
    return {
        "format": "v0.7",
        "result_file": str(path),
        "datasets": datasets,
        "parameters": pd.read_csv(parameter_path) if parameter_path and parameter_path.is_file() else None,
        "diagnostics": {
            key: value
            for key, value in doc.items()
            if key not in {"data", "scheme", "initial_parameters", "optimized_parameters", "parameter_history", "optimization_history"}
            and not isinstance(value, (dict, list))
        },
    }


def load_v08(root: Path) -> dict[str, Any]:
    path, doc = document(root)
    datasets: dict[str, Any] = {}
    for label, entry in (doc.get("optimization_results") or {}).items():
        dataset_root = root / "optimization_results" / label
        variables: dict[str, xr.DataArray] = {}
        files: list[str] = []
        for semantic, key, preferred in (
            ("data", "input_data", "data"),
            ("residual", "residuals", "residual"),
            ("fitted_data", "fitted_data", None),
        ):
            relative = entry.get(key)
            if relative:
                source = dataset_root / relative
                if source.is_file():
                    variables[semantic] = array_from_file(source, preferred)
                    files.append(str(source))
        for semantic in ("clp", "matrix"):
            relative = (entry.get("fit_decomposition") or {}).get(semantic)
            if relative:
                source = dataset_root / "fit_decomposition" / relative
                if source.is_file():
                    variables[semantic] = array_from_file(source)
                    files.append(str(source))
        datasets[label] = {
            "variables": variables,
            "metadata": entry.get("meta") or {},
            "source_files": files,
        }
    parameter_path = root / doc["optimized_parameters"] if doc.get("optimized_parameters") else None
    return {
        "format": "v0.8",
        "result_file": str(path),
        "datasets": datasets,
        "parameters": pd.read_csv(parameter_path) if parameter_path and parameter_path.is_file() else None,
        "diagnostics": doc.get("optimization_info") or {},
    }


def parameters(expected: pd.DataFrame | None, current: pd.DataFrame | None) -> dict[str, Any]:
    if expected is None or current is None or "label" not in expected or "label" not in current:
        return {"status": "missing"}
    left = expected.set_index("label")["value"]
    right = current.set_index("label")["value"]
    shared = left.index.intersection(right.index)
    missing_reference = sorted(set(right.index) - set(left.index))
    missing_staging = sorted(set(left.index) - set(right.index))
    if shared.empty:
        return {
            "status": "different",
            "shared_count": 0,
            "missing_reference": missing_reference,
            "missing_staging": missing_staging,
        }
    left_values = left.loc[shared].to_numpy(float)
    right_values = right.loc[shared].to_numpy(float)
    difference = np.abs(left_values - right_values)
    relative = difference / np.maximum(np.abs(left_values), np.finfo(float).eps)
    worst = int(np.nanargmax(relative))
    passed = bool(
        np.allclose(left_values, right_values, rtol=PARAMETER_RTOL, atol=PARAMETER_ATOL, equal_nan=True)
        and not missing_reference
        and not missing_staging
    )
    return {
        "status": "pass" if passed else "different",
        "shared_count": len(shared),
        "missing_reference": missing_reference,
        "missing_staging": missing_staging,
        "max_abs": float(np.nanmax(difference)),
        "max_relative": float(np.nanmax(relative)),
        "worst_label": str(shared[worst]),
    }


def metadata_metrics(expected: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    aliases = {
        "dataset_scale": ("dataset_scale", "scale"),
        "root_mean_square_error": ("root_mean_square_error",),
        "weighted_root_mean_square_error": ("weighted_root_mean_square_error",),
    }
    metrics: dict[str, Any] = {}
    for canonical, names in aliases.items():
        left = next((expected[name] for name in names if name in expected), None)
        right = next((current[name] for name in names if name in current), None)
        if left is None and right is None:
            continue
        if left is None or right is None:
            metrics[canonical] = {"status": "missing", "reference": left, "staging": right}
            continue
        try:
            difference = abs(float(left) - float(right))
            passed = bool(np.isclose(left, right, rtol=ARRAY_RTOL, atol=ARRAY_ATOL, equal_nan=True))
            metrics[canonical] = {
                "status": "pass" if passed else "different",
                "reference": float(left),
                "staging": float(right),
                "abs_difference": float(difference),
            }
        except (TypeError, ValueError):
            metrics[canonical] = {
                "status": "pass" if left == right else "different",
                "reference": left,
                "staging": right,
            }
    return metrics


def compare_leaf(relative: str, reference_root: Path, staging_root: Path) -> dict[str, Any]:
    record: dict[str, Any] = {
        "result": relative,
        "reference_path": str(reference_root),
        "staging_path": str(staging_root),
        "fitted_data_normalized_rms_tolerance": FIT_TOLERANCE,
        "parameter_tolerance": {"rtol": PARAMETER_RTOL, "atol": PARAMETER_ATOL},
    }
    try:
        reference = load_v07(reference_root)
        staging = load_v08(staging_root)
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        record.update({"status": "MISSING_ARTIFACT", "reason": repr(error)})
        return record
    datasets = []
    primary_failure = False
    secondary_difference = False
    for label in sorted(set(reference["datasets"]) | set(staging["datasets"])):
        if label not in reference["datasets"] or label not in staging["datasets"]:
            datasets.append({"dataset": label, "status": "MISSING_ARTIFACT"})
            primary_failure = True
            continue
        expected = reference["datasets"][label]
        current = staging["datasets"][label]
        variable_metrics: dict[str, Any] = {}
        for variable in ("data", "fitted_data", "residual", "clp", "matrix"):
            if variable not in expected["variables"] or variable not in current["variables"]:
                variable_metrics[variable] = {"status": "missing"}
                if variable in {"data", "fitted_data"}:
                    primary_failure = True
                else:
                    secondary_difference = True
                continue
            exact = variable == "data"
            metric = compare_arrays(
                expected["variables"][variable],
                current["variables"][variable],
                rtol=0.0 if exact else ARRAY_RTOL,
                atol=0.0 if exact else ARRAY_ATOL,
            )
            variable_metrics[variable] = metric
            if variable == "data" and metric.get("status") != "pass":
                primary_failure = True
            elif variable == "fitted_data" and (
                metric.get("status") == "structural_mismatch"
                or metric.get("normalized_rms", float("inf")) > FIT_TOLERANCE
            ):
                primary_failure = True
            elif variable not in {"data", "fitted_data"} and metric.get("status") != "pass":
                secondary_difference = True
        metadata = metadata_metrics(expected["metadata"], current["metadata"])
        if any(metric["status"] != "pass" for metric in metadata.values()):
            secondary_difference = True
        datasets.append(
            {
                "dataset": label,
                "status": "compared",
                "variables": variable_metrics,
                "reference_metadata": expected["metadata"],
                "staging_metadata": current["metadata"],
                "metadata": metadata,
                "reference_source_files": expected["source_files"],
                "staging_source_files": current["source_files"],
            }
        )
    parameter_metrics = parameters(reference["parameters"], staging["parameters"])
    if parameter_metrics["status"] != "pass":
        secondary_difference = True
    diagnostics = {
        "reference": reference["diagnostics"],
        "staging": staging["diagnostics"],
        "function_evaluations": {
            "reference": reference["diagnostics"].get("number_of_function_evaluations"),
            "staging": staging["diagnostics"].get("number_of_function_evaluations"),
        },
        "fit_success": {
            "reference": reference["diagnostics"].get("success"),
            "staging": staging["diagnostics"].get("success"),
        },
    }
    if diagnostics["function_evaluations"]["reference"] != diagnostics["function_evaluations"]["staging"]:
        secondary_difference = True
    if primary_failure:
        status = "REVIEW_REQUIRED"
        reason = "an exact-input or fitted-data primary comparison requires review"
    elif secondary_difference:
        status = "REVIEW_REQUIRED"
        reason = "primary fit evidence meets tolerance; secondary evidence differs or is missing"
    else:
        status = "PASS"
        reason = "automated semantic comparisons meet the provisional thresholds"
    record.update(
        {
            "status": status,
            "reason": reason,
            "datasets": datasets,
            "parameters": parameter_metrics,
            "diagnostics": diagnostics,
            "provenance": {
                "reference_result_file": reference["result_file"],
                "staging_result_file": staging["result_file"],
            },
        }
    )
    return record


def compare(reference: Path, staging: Path, slug: str) -> dict[str, Any]:
    reference_leaves = result_roots(reference)
    staging_leaves = result_roots(staging)
    records = []
    if not reference_leaves and not staging_leaves:
        records.append(
            {
                "result": "[no-result-leaves]",
                "status": "MISSING_ARTIFACT",
                "reference_present": False,
                "staging_present": False,
            }
        )
    for relative in sorted(set(reference_leaves) | set(staging_leaves)):
        if relative not in reference_leaves or relative not in staging_leaves:
            records.append(
                {
                    "result": relative,
                    "status": "MISSING_ARTIFACT",
                    "reference_present": relative in reference_leaves,
                    "staging_present": relative in staging_leaves,
                }
            )
            continue
        records.append(compare_leaf(relative, reference_leaves[relative], staging_leaves[relative]))
    counts = {
        status: sum(record["status"] == status for record in records)
        for status in ("PASS", "REVIEW_REQUIRED", "MISSING_ARTIFACT")
    }
    provisional = "MISSING_ARTIFACT" if counts["MISSING_ARTIFACT"] else (
        "REVIEW_REQUIRED" if counts["REVIEW_REQUIRED"] else "PASS"
    )
    return {
        "version": 1,
        "slug": slug,
        "reference_root": str(reference),
        "staging_root": str(staging),
        "thresholds": {
            "fitted_data_normalized_rms": FIT_TOLERANCE,
            "array_rtol": ARRAY_RTOL,
            "array_atol": ARRAY_ATOL,
            "parameter_rtol": PARAMETER_RTOL,
            "parameter_atol": PARAMETER_ATOL,
        },
        "results": records,
        "summary": {
            "reference_result_count": len(reference_leaves),
            "staging_result_count": len(staging_leaves),
            "status_counts": counts,
            "provisional_status": provisional,
        },
        "classification_notice": "Automated, provisional evidence only; no scientific parity or root-cause classification is assigned.",
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Provisional semantic comparison: {report['slug']}",
        "",
        report["classification_notice"],
        "",
        "| Result leaf | Status | Worst fitted-data normalized RMS | Function evaluations (v0.7/v0.8) |",
        "|---|---|---:|---|",
    ]
    for record in report["results"]:
        fits = [
            dataset.get("variables", {}).get("fitted_data", {}).get("normalized_rms")
            for dataset in record.get("datasets", [])
        ]
        worst = max((value for value in fits if value is not None), default="n/a")
        evaluations = record.get("diagnostics", {}).get("function_evaluations", {})
        lines.append(
            f"| {record['result']} | **{record['status']}** | {worst} | "
            f"{evaluations.get('reference', 'n/a')}/{evaluations.get('staging', 'n/a')} |"
        )
    lines.extend(
        [
            "",
            f"Provisional repository status: **{report['summary']['provisional_status']}**.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare(args.reference.resolve(), args.staging.resolve(), args.slug)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    args.output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))
    return 1 if report["summary"]["provisional_status"] == "MISSING_ARTIFACT" else 0


if __name__ == "__main__":
    raise SystemExit(main())
