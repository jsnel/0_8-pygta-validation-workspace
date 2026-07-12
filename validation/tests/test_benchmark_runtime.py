from __future__ import annotations

import json
import math
import sys
import time
import types
from pathlib import Path

import pytest

from validation import benchmark_hooks
from validation.benchmark_runtime import (
    aggregate_report,
    load_benchmark_manifest,
    notebook_fit_cells,
    write_report,
)


def test_benchmark_manifest_has_expected_fit_calls_and_valid_selectors() -> None:
    workspace = Path(__file__).parents[2]
    manifest, _ = load_benchmark_manifest(workspace / "validation/benchmarks.yml")
    assert len(manifest["cases"]) == 15
    assert {case["id"] for case in manifest["cases"]} >= {
        "study_fluorescence/global",
        "study_fluorescence/target",
        "ex_spectral_constraints/with_penalties",
    }

    import nbformat

    for branch, checkout in (("main", "pyglotaran-main-dev"), ("staging", "pyglotaran-staging-dev")):
        root = workspace / f"temp/{checkout}/pyglotaran-examples/pyglotaran_examples"
        for notebook in sorted({case["notebook"] for case in manifest["cases"]}):
            with (root / notebook).open(encoding="utf-8") as stream:
                loaded = nbformat.read(stream, as_version=4)
            selected, last_index = notebook_fit_cells(loaded, manifest, branch, notebook)
            assert selected
            assert last_index >= max(item["cell_index"] for item in selected.values())


def _fake_main_modules(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    glotaran = types.ModuleType("glotaran")
    optimization = types.ModuleType("glotaran.optimization")
    optimize_module = types.ModuleType("glotaran.optimization.optimize")

    def optimize(*args: object, **kwargs: object) -> object:
        return {"optimization_info": {"number_of_function_evaluations": 3}}

    optimize_module.optimize = optimize  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "glotaran", glotaran)
    monkeypatch.setitem(sys.modules, "glotaran.optimization", optimization)
    monkeypatch.setitem(sys.modules, "glotaran.optimization.optimize", optimize_module)
    return optimize_module


def test_main_public_fit_hook_records_only_optimizer_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _fake_main_modules(monkeypatch)
    benchmark_hooks._STATE = None
    record_path = tmp_path / "calls.json"
    benchmark_hooks.install("main", str(record_path))
    module.optimize()  # type: ignore[attr-defined]
    time.sleep(0.01)  # represents save/plot work after the fit cell
    records = json.loads(record_path.read_text(encoding="utf-8"))
    assert len(records) == 1
    assert records[0]["entrypoint"] == "glotaran.optimization.optimize.optimize"
    assert records[0]["success"] is True
    assert records[0]["duration_seconds"] < 0.01
    assert records[0]["workload"]["number_of_function_evaluations"] == 3
    benchmark_hooks._STATE = None


def test_staging_public_fit_hook_patches_scheme_method(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    glotaran = types.ModuleType("glotaran")
    project = types.ModuleType("glotaran.project")
    scheme_module = types.ModuleType("glotaran.project.scheme")

    class Scheme:
        def optimize(self, *args: object, **kwargs: object) -> object:
            return {"number_of_function_evaluations": kwargs.get("maximum_number_function_evaluations", 2)}

    scheme_module.Scheme = Scheme  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "glotaran", glotaran)
    monkeypatch.setitem(sys.modules, "glotaran.project", project)
    monkeypatch.setitem(sys.modules, "glotaran.project.scheme", scheme_module)
    benchmark_hooks._STATE = None
    record_path = tmp_path / "calls.json"
    benchmark_hooks.install("staging", str(record_path))
    Scheme().optimize(maximum_number_function_evaluations=4)
    records = json.loads(record_path.read_text(encoding="utf-8"))
    assert records[0]["entrypoint"] == "glotaran.project.scheme.Scheme.optimize"
    assert records[0]["workload"]["number_of_function_evaluations"] == 4
    benchmark_hooks._STATE = None


def _synthetic_runs(tmp_path: Path) -> tuple[Path, Path]:
    workspace = Path(__file__).parents[2]
    manifest_path = workspace / "validation/benchmarks.yml"
    manifest, _ = load_benchmark_manifest(manifest_path)
    raw_root = tmp_path / "raw"
    for repetition in range(1, 6):
        for branch in ("main", "staging"):
            run_dir = raw_root / branch / f"repetition-{repetition:02d}"
            notebooks = []
            for case in manifest["cases"]:
                duration = repetition if branch == "main" else repetition + 1
                notebooks.append(
                    {
                        "path": case["notebook"],
                        "status": "passed",
                        "fit_calls": [
                            {
                                "fit_id": case["id"],
                                "scenario": case["scenario"],
                                "notebook": case["notebook"],
                                "cell_id": case[branch]["cell_id"],
                                "invocation": case[branch]["invocation"],
                                "duration_ns": duration * 1_000_000_000,
                                "duration_seconds": float(duration),
                                "success": True,
                                "workload": {
                                    "number_of_function_evaluations": 10,
                                },
                            }
                        ],
                    }
                )
            (run_dir / "run.json").parent.mkdir(parents=True, exist_ok=True)
            (run_dir / "run.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "branch": branch,
                        "repetition": repetition,
                        "warmup": False,
                        "status": "passed",
                        "notebooks": notebooks,
                    }
                ),
                encoding="utf-8",
            )
    for branch in ("main", "staging"):
        warmup_dir = raw_root / branch / "warmup-01"
        warmup_dir.mkdir(parents=True, exist_ok=True)
        (warmup_dir / "run.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "branch": branch,
                    "repetition": 1,
                    "warmup": True,
                    "status": "passed",
                    "notebooks": [],
                }
            ),
            encoding="utf-8",
        )
    return raw_root, manifest_path


def test_aggregate_report_uses_sample_standard_deviation(tmp_path: Path) -> None:
    raw_root, manifest_path = _synthetic_runs(tmp_path)
    manifest, _ = load_benchmark_manifest(manifest_path)
    report = aggregate_report(raw_root, manifest_path, manifest)
    summary = report["summaries"][0]
    assert summary["main"]["mean_seconds"] == 3.0
    assert math.isclose(summary["main"]["std_seconds"], math.sqrt(2.5))
    assert summary["staging"]["mean_seconds"] == 4.0
    assert summary["ratio_staging_over_main"] == 4 / 3
    assert summary["workload_match"] is True
    assert report["measurement"]["comparison_layer_used"] is False


def test_report_rejects_incomplete_timed_samples(tmp_path: Path) -> None:
    raw_root, manifest_path = _synthetic_runs(tmp_path)
    broken = raw_root / "main" / "repetition-05" / "run.json"
    document = json.loads(broken.read_text(encoding="utf-8"))
    document["notebooks"][0]["fit_calls"] = []
    broken.write_text(json.dumps(document), encoding="utf-8")
    manifest, _ = load_benchmark_manifest(manifest_path)
    with pytest.raises(ValueError, match="expected 5 timed samples"):
        aggregate_report(raw_root, manifest_path, manifest)


def test_report_writes_csv_json_and_plots(tmp_path: Path) -> None:
    raw_root, manifest_path = _synthetic_runs(tmp_path)
    manifest, _ = load_benchmark_manifest(manifest_path)
    report = aggregate_report(raw_root, manifest_path, manifest)
    output = tmp_path / "report"
    write_report(report, output)
    for filename in ("runtime.json", "runtime.csv", "runtime.png", "runtime.svg"):
        assert (output / filename).is_file()
