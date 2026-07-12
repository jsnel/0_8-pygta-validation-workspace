"""Create an impact-ranked analysis of a v0.7/v0.8 comparison run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import yaml

from compare_results import dataset_labels
from compare_results import locate_main_dataset
from compare_results import scenario_map


DIMENSION_ALIASES = {
    "amplitude_label": "clp_label",
    "amplitude": "clp",
}


def read_result_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def first_variable(dataset: xr.Dataset, preferred: str | None = None) -> xr.DataArray:
    if preferred and preferred in dataset.data_vars:
        return dataset[preferred]
    return dataset[next(iter(dataset.data_vars))]


def load_array(path: Path, preferred: str | None = None) -> xr.DataArray:
    with xr.open_dataset(path) as dataset:
        return first_variable(dataset, preferred).load()


def canonical_array(array: xr.DataArray) -> xr.DataArray:
    rename = {old: new for old, new in DIMENSION_ALIASES.items() if old in array.dims}
    return array.rename(rename) if rename else array


def array_metrics(expected: xr.DataArray, current: xr.DataArray) -> dict[str, object]:
    expected = canonical_array(expected)
    current = canonical_array(current)
    record: dict[str, object] = {
        "expected_dims": list(expected.dims),
        "current_dims": list(current.dims),
        "expected_shape": list(expected.shape),
        "current_shape": list(current.shape),
    }
    if set(expected.dims) == set(current.dims) and expected.dims != current.dims:
        current = current.transpose(*expected.dims)
        record["transposed_for_comparison"] = True
    if expected.shape != current.shape or expected.dims != current.dims:
        record["status"] = "structural_mismatch"
        return record
    expected_values = np.asarray(expected.values)
    current_values = np.asarray(current.values)
    difference = np.abs(expected_values - current_values)
    data_rms = float(np.sqrt(np.nanmean(expected_values**2))) if expected_values.size else 0.0
    diff_rms = float(np.sqrt(np.nanmean(difference**2))) if difference.size else 0.0
    max_abs = float(np.nanmax(difference)) if difference.size else 0.0
    record.update(
        {
            "status": "pass" if np.allclose(expected_values, current_values, rtol=1e-5, atol=1e-8) else "different",
            "max_abs": max_abs,
            "diff_rms": diff_rms,
            "expected_rms": data_rms,
            "diff_rms_over_expected_rms": diff_rms / max(data_rms, np.finfo(float).eps),
            "expected_max_abs": float(np.nanmax(np.abs(expected_values))) if expected_values.size else 0.0,
        }
    )
    return record


def staging_file_for(staging_dataset: Path, variable: str) -> tuple[Path, str | None]:
    mapping = {
        "data": (staging_dataset / "input_data.nc", "data"),
        "residual": (staging_dataset / "residuals.nc", "residual"),
        "fitted_data": (staging_dataset / "fitted_data.nc", None),
        "clp": (staging_dataset / "fit_decomposition/clp.nc", None),
        "matrix": (staging_dataset / "fit_decomposition/matrix.nc", None),
    }
    return mapping[variable]


def main_variable_for(variable: str) -> str:
    return {
        "data": "data",
        "residual": "residual",
        "fitted_data": "fitted_data",
        "clp": "clp",
        "matrix": "matrix",
    }[variable]


def parameter_metrics(main_scenario: Path, staging_scenario: Path) -> dict[str, object]:
    main_file = main_scenario / "optimized_parameters.csv"
    staging_file = staging_scenario / "optimized_parameters.csv"
    if not main_file.is_file() or not staging_file.is_file():
        return {"status": "missing", "main_file": str(main_file), "staging_file": str(staging_file)}
    expected = pd.read_csv(main_file, index_col="label")["value"]
    current = pd.read_csv(staging_file, index_col="label")["value"]
    shared = expected.index.intersection(current.index)
    missing_in_main = sorted(set(current.index) - set(expected.index))
    missing_in_staging = sorted(set(expected.index) - set(current.index))
    if not len(shared):
        return {
            "status": "different",
            "shared_count": 0,
            "missing_in_main": missing_in_main,
            "missing_in_staging": missing_in_staging,
        }
    expected_values = expected.loc[shared].to_numpy(dtype=float)
    current_values = current.loc[shared].to_numpy(dtype=float)
    difference = np.abs(expected_values - current_values)
    relative = difference / np.maximum(np.abs(expected_values), np.finfo(float).eps)
    worst = int(np.argmax(relative))
    close = bool(np.allclose(expected_values, current_values, rtol=1e-5, atol=1e-8))
    return {
        "status": "pass" if close and not missing_in_main and not missing_in_staging else "different",
        "shared_count": len(shared),
        "missing_in_main": missing_in_main,
        "missing_in_staging": missing_in_staging,
        "max_abs": float(np.max(difference)),
        "max_relative": float(np.max(relative)),
        "worst_label": str(shared[worst]),
        "worst_main_value": float(expected_values[worst]),
        "worst_staging_value": float(current_values[worst]),
    }


def metadata_metrics(main_dataset: Path, staging_dataset: Path, staging_meta: dict) -> dict[str, object]:
    with xr.open_dataset(main_dataset) as dataset:
        main_attrs = dict(dataset.attrs)
    key_pairs = (
        ("root_mean_square_error", "root_mean_square_error"),
        ("weighted_root_mean_square_error", "weighted_root_mean_square_error"),
        ("dataset_scale", "scale"),
    )
    comparisons = {}
    for main_key, staging_key in key_pairs:
        main_value = main_attrs.get(main_key)
        staging_value = staging_meta.get(staging_key)
        if main_value is None and staging_value is None:
            continue
        if main_value is None or staging_value is None:
            if main_key == "dataset_scale" and main_value is not None and np.isclose(main_value, 1.0):
                # v0.8 omits the default scale from result metadata.
                continue
            comparisons[main_key] = {
                "status": "missing",
                "main": main_value,
                "staging": staging_value,
            }
            continue
        difference = abs(float(main_value) - float(staging_value))
        comparisons[main_key] = {
            "status": "pass" if np.isclose(main_value, staging_value, rtol=1e-5, atol=1e-8) else "different",
            "main": float(main_value),
            "staging": float(staging_value),
            "abs_difference": float(difference),
        }
    return comparisons


def scenario_metrics(main_scenario: Path, staging_scenario: Path) -> dict[str, object]:
    datasets: list[dict[str, object]] = []
    staging_result = read_result_yaml(staging_scenario / "result.yml")
    staging_result_datasets = staging_result.get("optimization_results") or {}
    for label in dataset_labels(staging_scenario):
        main_dataset = locate_main_dataset(main_scenario, label)
        staging_dataset = staging_scenario / "optimization_results" / label
        if main_dataset is None:
            datasets.append({"dataset": label, "status": "missing_main_dataset"})
            continue
        variables: dict[str, object] = {}
        for variable in ("data", "residual", "fitted_data", "clp", "matrix"):
            main_path = main_dataset
            staging_path, staging_variable = staging_file_for(staging_dataset, variable)
            if not main_path.is_file() or not staging_path.is_file():
                variables[variable] = {"status": "missing"}
                continue
            try:
                variables[variable] = array_metrics(
                    load_array(main_path, main_variable_for(variable)),
                    load_array(staging_path, staging_variable),
                )
            except (KeyError, OSError, ValueError) as error:
                variables[variable] = {"status": "unreadable", "error": repr(error)}
        datasets.append(
            {
                "dataset": label,
                "status": "compared",
                "variables": variables,
                "metadata": metadata_metrics(
                    main_dataset,
                    staging_dataset,
                    (staging_result_datasets.get(label) or {}).get("meta") or {},
                ),
            }
        )

    return {
        "parameters": parameter_metrics(main_scenario, staging_scenario),
        "datasets": datasets,
    }


def impact_for(details: dict[str, object]) -> tuple[str, float]:
    datasets = details["datasets"]
    missing = details["parameters"].get("status") == "missing" or any(
        dataset.get("status") != "compared" for dataset in datasets
    )
    if missing:
        return "coverage/artifact", 1000.0
    fitted = [
        variable
        for dataset in datasets
        for name, variable in dataset["variables"].items()
        if name == "fitted_data" and variable.get("status") in {"pass", "different"}
    ]
    parameter_relative = float(details["parameters"].get("max_relative", 0.0) or 0.0)
    parameter_absolute = float(details["parameters"].get("max_abs", 0.0) or 0.0)
    fit_relative = max((float(item.get("diff_rms_over_expected_rms", 0.0)) for item in fitted), default=0.0)
    if fit_relative >= 1e-3:
        category = "scientific fit"
        score = 700.0 + min(300.0, 100.0 * np.log10(1.0 + fit_relative / 1e-3))
    elif parameter_absolute >= 1e6:
        category = "parameter pathology"
        score = 650.0 + min(250.0, 25.0 * np.log10(1.0 + parameter_absolute))
    elif parameter_relative >= 1e-3:
        category = "parameter/recovery"
        score = 400.0 + min(200.0, 100.0 * np.log10(1.0 + parameter_relative / 1e-3))
    else:
        category = "small numerical or structural"
        score = max(100.0 * min(parameter_relative / 1e-3, 1.0), 1000.0 * min(fit_relative / 1e-3, 1.0))
    return category, float(score)


def make_report(main_root: Path, staging_root: Path) -> dict[str, object]:
    main_scenarios = scenario_map(main_root)
    staging_scenarios = scenario_map(staging_root)
    common = sorted(set(main_scenarios) & set(staging_scenarios))
    scenarios = {
        name: scenario_metrics(main_scenarios[name], staging_scenarios[name]) for name in common
    }
    ranked = []
    for name, details in scenarios.items():
        category, score = impact_for(details)
        ranked.append({"scenario": name, "category": category, "impact_score": score, **details})
    ranked.sort(key=lambda item: item["impact_score"], reverse=True)
    root_cause_groups = [
        {
            "priority": 1,
            "group": "translated input mismatch in transient-absorption target",
            "evidence": "v0.7 weight 0.2 versus staging weight 0.1 for global interval [720, 890]",
            "impact": "fit and parameter differences; resolve input inequivalence first",
        },
        {
            "priority": 2,
            "group": "unbounded or ill-conditioned rates.k3d2 path",
            "evidence": "approximately 1.25e7 in v0.7 versus 1.94e25 in staging with nearly equal fit quality",
            "impact": "severe parameter reproducibility issue, low current fit-quality impact",
        },
        {
            "priority": 3,
            "group": "result-artifact coverage and persistence mapping",
            "evidence": "missing staging ex_doas result and collapsed spectral-constraints result variants",
            "impact": "blocks complete comparison coverage",
        },
        {
            "priority": 4,
            "group": "missing weighted-RMSE diagnostics",
            "evidence": "15 staging dataset metadata entries omit weighted_root_mean_square_error present in v0.7",
            "impact": "cross-cutting reporting regression for weighted analyses",
        },
        {
            "priority": 5,
            "group": "spectral-guidance parameter and decomposition difference",
            "evidence": "rates.k2 relative delta 3.679e-3 while fitted-data normalized RMS delta is 2.519e-7",
            "impact": "parameter/decomposition issue with low fit-quality impact",
        },
        {
            "priority": 6,
            "group": "weighted/scale numerical drift",
            "evidence": "3d weighted fitted-data normalized RMS delta 2.446e-5 and scale.3 relative delta 2.596e-5",
            "impact": "low numerical impact; useful controlled weight/scale case",
        },
        {
            "priority": 7,
            "group": "structural result-schema differences",
            "evidence": "clp_label/amplitude_label aliases and split result files",
            "impact": "mostly adapter and compatibility work",
        },
    ]
    return {
        "method": {
            "comparison": "canonical dimension aliases plus normalized RMS and labeled parameter deltas",
            "relative_fit_scale": "difference RMS / v0.7 expected-array RMS",
            "parameter_tolerance": {"rtol": 1e-5, "atol": 1e-8},
            "impact_score": "triage ordering only; 1000 means coverage/artifact gap, scientific scores scale with normalized fit or parameter differences",
        },
        "coverage": {
            "common_scenarios": common,
            "missing_in_main": sorted(set(staging_scenarios) - set(main_scenarios)),
            "missing_in_staging": sorted(set(main_scenarios) - set(staging_scenarios)),
        },
        "root_cause_groups": root_cause_groups,
        "ranked_scenarios": ranked,
    }


def markdown(report: dict[str, object]) -> str:
    lines = [
        "# Detailed v0.7.4 vs v0.8 staging issue report",
        "",
        "This is a triage report from the retained notebook outputs. It ranks observed differences; it does not yet prove that every difference is a staging bug.",
        "",
        "## Impact ranking",
        "",
        "| Rank | Scenario | Category | Score | Max fitted-data RMS ratio | Max parameter relative delta |",
        "|---:|---|---|---:|---:|---:|",
    ]
    for index, item in enumerate(report["ranked_scenarios"], 1):
        fit_ratios = [
            float(variable.get("diff_rms_over_expected_rms", 0.0))
            for dataset in item["datasets"]
            if dataset.get("status") == "compared"
            for name, variable in dataset["variables"].items()
            if name == "fitted_data" and variable.get("status") in {"pass", "different"}
        ]
        lines.append(
            f"| {index} | `{item['scenario']}` | {item['category']} | {item['impact_score']:.1f} | {max(fit_ratios, default=0.0):.3e} | {float(item['parameters'].get('max_relative', 0.0) or 0.0):.3e} |"
        )
    lines += [
        "",
        "## Root-cause ranking",
        "",
        "| Priority | Root-cause group | Evidence and scope | Impact interpretation |",
        "|---:|---|---|---|",
        "| 1 | Translated input mismatch in transient-absorption target | The v0.7 model records weight `0.2` for global interval `[720, 890]`, while the staging scheme records `0.1`; target fitted-data normalized RMS difference is `2.785e-3`, with a `25.2%` maximum parameter-relative delta. | Confirmed input inequivalence; fix or explicitly accept before diagnosing optimizer behavior. |",
        "| 2 | Unbounded/ill-conditioned `rates.k3d2` path | In `study_transient_absorption/two_dataset_analysis`, v0.7 ends at about `1.25e7`, staging at `1.94e25`; fitted-data normalized RMS difference is only `1.383e-5` and chi-square is effectively equal. | Severe parameter-reporting/reproducibility issue, but not currently a large fit-quality issue. |",
        "| 3 | Result-artifact coverage and persistence mapping | Staging has no saved `ex_doas_beta` result, and its spectral-constraints output does not preserve the four v0.7 result variants as separate comparable leaves. | Blocks complete validation coverage and can create false regression counts. |",
        "| 4 | Missing weighted-RMSE diagnostics | `weighted_root_mean_square_error` is absent from 15 staging dataset metadata entries where v0.7 contains it. | Cross-cutting reporting regression, especially relevant to weighted analyses; does not by itself prove numerical divergence. |",
        "| 5 | Spectral-guidance parameter/decomposition difference | `rates.k2` differs by `3.679e-3` relative while fitted-data normalized RMS difference is `2.519e-7`; CLP/matrix decomposition differences are much larger than the reconstructed fit difference. | Likely parameter identifiability, model translation, or decomposition convention; lower fit-quality impact. |",
        "| 6 | Weighted/scale numerical drift | `simultaneous_analysis_3d_weight` has a largest fitted-data normalized RMS difference of `2.446e-5` and `scale.3` delta of `2.596e-5`; chi-square is effectively equal. | Low numerical impact, but a useful controlled case for weight/scale handling. |",
        "| 7 | Structural result-schema differences | Common `clp`/`matrix` dimensions use aliases such as `clp_label` versus `amplitude_label`, and staging splits rich v0.7 datasets across multiple files. | Mostly compatibility/adapter work once label-aware comparisons are in place. |",
    ]
    lines += ["", "## Coverage and structural issues", ""]
    lines.append(f"Common leaf scenarios compared: **{len(report['coverage']['common_scenarios'])}**.")
    lines.append(f"Missing in main: `{', '.join(report['coverage']['missing_in_main']) or 'none'}`.")
    lines.append(f"Missing in staging: `{', '.join(report['coverage']['missing_in_staging']) or 'none'}`.")
    lines += [
        "",
        "The staging result layout is not a one-to-one file translation: it splits each dataset into input, residual, fitted-data, decomposition, activation, and element files. Dimension aliases such as `amplitude_label`/`clp_label` are canonicalized for numeric triage, but their coordinate values still need a label-level review.",
        "",
        "## Scenario evidence",
    ]
    for item in report["ranked_scenarios"]:
        lines += ["", f"### `{item['scenario']}` — {item['category']}", ""]
        params = item["parameters"]
        lines.append(
            f"Parameters: `{params.get('status')}`; shared={params.get('shared_count', 0)}, max absolute delta={params.get('max_abs', 'n/a')}, max relative delta={params.get('max_relative', 'n/a')}, worst label=`{params.get('worst_label', 'n/a')}`."
        )
        for dataset in item["datasets"]:
            if dataset.get("status") != "compared":
                lines.append(f"- `{dataset['dataset']}`: `{dataset['status']}`.")
                continue
            for variable, metrics in dataset["variables"].items():
                if metrics.get("status") in {"pass", "different"}:
                    lines.append(
                        f"- `{dataset['dataset']}/{variable}`: `{metrics['status']}`, max abs={metrics.get('max_abs', 'n/a'):.3e}, diff RMS={metrics.get('diff_rms', 'n/a'):.3e}, normalized diff RMS={metrics.get('diff_rms_over_expected_rms', 'n/a'):.3e}."
                    )
                elif metrics.get("status") == "structural_mismatch":
                    lines.append(
                        f"- `{dataset['dataset']}/{variable}`: structural-only mismatch after canonicalization; expected dims={metrics.get('expected_dims')}, staging dims={metrics.get('current_dims')}."
                    )
            for key, metrics in dataset.get("metadata", {}).items():
                if metrics.get("status") in {"different", "missing"}:
                    lines.append(
                        f"- `{dataset['dataset']}/metadata/{key}`: `{metrics['status']}`, main={metrics.get('main')}, staging={metrics.get('staging')}, absolute difference={metrics.get('abs_difference', 'n/a')}."
                    )
    lines += [
        "",
        "## Root-cause clusters to investigate",
        "",
        "1. **Result persistence and coverage:** staging does not emit a saved result for `ex_doas_beta`, and the spectral-constraints notebook collapses multiple v0.7 result variants into a different saved layout. Fixing the save/fixture mapping can remove several apparent missing-result issues without changing numerics.",
        "2. **Label/schema translation:** most `clp` and `matrix` observations are dimension-name mismatches (`clp_label` versus `amplitude_label`) rather than shape mismatches. A label-aware canonicalizer should separate harmless schema changes from actual array changes.",
        "3. **Weighted optimization path:** prioritize `simultaneous_analysis_3d_weight`, where the largest fitted-data absolute deviation occurs in the current evidence. Determine whether the difference comes from weight application, result unweighting, parameter convergence, or a changed example translation.",
        "4. **Translated-input mismatch:** the transient-absorption target translation changes the second spectral weight interval from `0.2` in v0.7 to `0.1` in staging. This is a concrete input difference and should be resolved before treating its output deltas as an optimizer regression.",
        "5. **Parameter pathology:** `rates.k3d2` in the two-dataset transient-absorption case moves from approximately `1.25×10^7` to `1.94×10^25` while chi-square and fitted-data RMS remain nearly unchanged. This points to an ill-conditioned or weakly identified parameter path and should be investigated separately from fit quality.",
        "6. **Scenario-specific convergence/model translation:** parameter differences and residual changes in spectral guidance and remaining transient-absorption cases need comparison of translated schemes, initial values, free-parameter labels, and termination conditions before assigning them to the optimizer.",
        "7. **Small numerical differences:** several linked/dispersion scenarios have fitted-data normalized RMS differences near or below machine/numerical tolerance while elementwise relative residual ratios look large because residual values are near zero. These should not drive root-cause prioritization.",
        "",
        "## Recommended next reduction pass",
        "",
        "1. Fix the result-artifact mapping and explicitly classify staging-only missing saves.",
        "2. Compare normalized scheme/parameter inputs before comparing outputs.",
        "3. Use fitted-data normalized RMS as the primary scientific-impact metric; use residuals and CLPs as secondary diagnostics.",
        "4. Start with the highest-impact weighted scenario, then the largest normalized fitted-data differences, and only afterward investigate parameter-only differences with nearly identical fits.",
        "5. Add one focused reproducible test per confirmed root cause, not per output file difference.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-root", type=Path, required=True)
    parser.add_argument("--staging-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = make_report(args.main_root.resolve(), args.staging_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            report,
            indent=2,
            default=lambda value: value.item() if hasattr(value, "item") else str(value),
        ),
        encoding="utf-8",
    )
    args.output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
