"""Benchmark public fit-call runtimes for the pinned example notebooks.

The ``run`` command launches one fresh worker process for each branch and
repetition. Workers execute the pinned notebooks in memory and install the
validation-only hooks from :mod:`benchmark_hooks`. The ``report`` command
aggregates the raw run manifests and creates the runtime comparison plot.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import traceback
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nbformat
import yaml
from nbclient import NotebookClient

try:
    from run_examples import (
        NOTEBOOKS,
        file_sha256,
        git_revision,
        installed_source_manifests,
        package_version,
        tree_sha256,
    )
except ImportError:  # pragma: no cover - used when imported as validation.*
    from validation.run_examples import (
        NOTEBOOKS,
        file_sha256,
        git_revision,
        installed_source_manifests,
        package_version,
        tree_sha256,
    )


ROOT = Path(__file__).resolve().parent.parent
THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMBA_NUM_THREADS",
)


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def load_benchmark_manifest(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and validate the benchmark and referenced scenario manifests."""

    document = read_yaml(path)
    if document.get("version") != 1:
        raise ValueError("Benchmark manifest must have version: 1")
    defaults = document.get("defaults") or {}
    repetitions = defaults.get("repetitions")
    warmups = defaults.get("warmups")
    if not isinstance(repetitions, int) or repetitions < 1:
        raise ValueError("defaults.repetitions must be a positive integer")
    if not isinstance(warmups, int) or warmups < 0:
        raise ValueError("defaults.warmups must be a non-negative integer")
    if defaults.get("timing") != "public_fit_call":
        raise ValueError("Only public_fit_call timing is supported")

    branches = document.get("branches") or {}
    if set(branches) != {"main", "staging"}:
        raise ValueError("Benchmark manifest must define main and staging branches")
    for branch, details in branches.items():
        if not details.get("label") or not details.get("entrypoint"):
            raise ValueError(f"Branch {branch!r} needs label and entrypoint")

    scenario_path = (path.parent / document.get("scenario_manifest", "scenarios.yml")).resolve()
    scenarios = read_yaml(scenario_path)
    scenario_ids = {item["id"] for item in scenarios.get("scenarios", [])}
    cases = document.get("cases") or []
    if not cases:
        raise ValueError("Benchmark manifest contains no cases")
    expected_count = document.get("expected_fit_calls")
    if expected_count is not None and len(cases) != expected_count:
        raise ValueError(f"Expected {expected_count} fit cases, found {len(cases)}")

    seen_ids: set[str] = set()
    for case in cases:
        case_id = case.get("id")
        if not case_id or case_id in seen_ids:
            raise ValueError(f"Duplicate or missing benchmark case ID: {case_id!r}")
        seen_ids.add(case_id)
        if case.get("scenario") not in scenario_ids:
            raise ValueError(f"Benchmark case {case_id!r} references an unknown scenario")
        notebook = case.get("notebook")
        if notebook not in NOTEBOOKS:
            raise ValueError(f"Benchmark case {case_id!r} references unknown notebook {notebook!r}")
        for branch in branches:
            selector = case.get(branch) or {}
            if not selector.get("cell_id") or not isinstance(selector.get("invocation"), int):
                raise ValueError(f"Case {case_id!r} needs {branch}.cell_id and invocation")
            if selector["invocation"] < 1:
                raise ValueError(f"Case {case_id!r} has a non-positive invocation")

    for branch in branches:
        by_notebook: dict[str, list[int]] = {}
        for case in cases:
            by_notebook.setdefault(case["notebook"], []).append(case[branch]["invocation"])
        for notebook, invocations in by_notebook.items():
            expected = list(range(1, max(invocations) + 1))
            if sorted(invocations) != expected:
                raise ValueError(
                    f"{branch} invocations for {notebook} must be contiguous from 1: {invocations}"
                )
    return document, scenarios


def cases_for_notebook(manifest: dict[str, Any], branch: str, notebook: str) -> list[dict[str, Any]]:
    cases = [case for case in manifest["cases"] if case["notebook"] == notebook]
    return sorted(cases, key=lambda case: case[branch]["invocation"])


def notebook_fit_cells(
    notebook: nbformat.NotebookNode,
    manifest: dict[str, Any],
    branch: str,
    notebook_path: str,
) -> tuple[dict[int, dict[str, Any]], int]:
    """Validate selectors and return invocation metadata plus last fit index."""

    cell_by_id = {
        str(cell.get("id")): (index, cell)
        for index, cell in enumerate(notebook.cells)
        if cell.get("id") is not None
    }
    selected: dict[int, dict[str, Any]] = {}
    for case in cases_for_notebook(manifest, branch, notebook_path):
        selector = case[branch]
        cell_id = str(selector["cell_id"])
        if cell_id not in cell_by_id:
            raise ValueError(f"{branch}: {notebook_path} has no cell ID {cell_id}")
        index, cell = cell_by_id[cell_id]
        source = cell.get("source", "")
        if "optimize" not in source:
            raise ValueError(f"{branch}: selected cell {cell_id} has no optimizer call")
        invocation = selector["invocation"]
        if invocation in selected:
            raise ValueError(f"Duplicate invocation {invocation} in {branch}:{notebook_path}")
        selected[invocation] = {
            "fit_id": case["id"],
            "scenario": case["scenario"],
            "cell_id": cell_id,
            "cell_index": index,
            "notebook": notebook_path,
        }
    return selected, max(item["cell_index"] for item in selected.values())


def benchmark_metadata(
    branch: str,
    examples_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    scenarios: dict[str, Any],
) -> dict[str, Any]:
    return {
        "branch": branch,
        "branch_label": manifest["branches"][branch]["label"],
        "entrypoint": manifest["branches"][branch]["entrypoint"],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "thread_environment": {name: os.environ.get(name) for name in THREAD_VARIABLES},
        "pyglotaran": package_version("pyglotaran"),
        "pyglotaran_extras": package_version("pyglotaran-extras"),
        "installed_source_manifests": installed_source_manifests(),
        "examples_root": str(examples_root.resolve()),
        "examples_revision": git_revision(examples_root),
        "examples_tree_sha256": tree_sha256(examples_root),
        "benchmark_manifest_sha256": sha256_file(manifest_path),
        "scenario_pinned_commits": scenarios.get("pinned_commits", {}),
    }


def isolated_environment(home_root: Path, threads: int) -> dict[str, str]:
    environment = os.environ.copy()
    environment["USERPROFILE"] = str(home_root)
    environment["HOME"] = str(home_root)
    drive, path = os.path.splitdrive(str(home_root))
    environment["HOMEDRIVE"] = drive
    environment["HOMEPATH"] = path
    environment["MPLBACKEND"] = "Agg"
    for name in THREAD_VARIABLES:
        environment[name] = str(threads)
    workspace = str(ROOT)
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = workspace + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    return environment


def prelude(branch: str, record_path: Path) -> str:
    return (
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "from validation.benchmark_hooks import install\n"
        f"install({branch!r}, {str(record_path)!r})\n"
    )


def execute_worker_notebook(
    source: Path,
    output_dir: Path,
    branch: str,
    manifest: dict[str, Any],
    notebook_path: str,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": notebook_path,
        "source": str(source),
        "source_sha256": sha256_file(source),
        "status": "failed",
        "fit_calls": [],
    }
    if not source.is_file():
        record["error"] = f"Missing notebook: {source}"
        return record
    record_path = output_dir / "calls" / (notebook_path.replace("/", "__") + ".json")
    try:
        with source.open(encoding="utf-8") as stream:
            notebook = nbformat.read(stream, as_version=4)
        selected, last_fit_index = notebook_fit_cells(notebook, manifest, branch, notebook_path)
        original_cells = deepcopy(notebook.cells[: last_fit_index + 1])
        notebook.cells = [nbformat.v4.new_code_cell(source=prelude(branch, record_path))] + original_cells
        NotebookClient(
            notebook,
            timeout=None,
            kernel_name="python3",
            resources={"metadata": {"path": str(source.parent)}},
        ).execute()
        record["status"] = "passed"
    except Exception as error:  # noqa: BLE001 - preserve notebook traceback
        record["error"] = repr(error)
        record["traceback"] = traceback.format_exc()

    raw_calls: list[dict[str, Any]] = []
    if record_path.is_file():
        raw_calls = json.loads(record_path.read_text(encoding="utf-8"))
    expected_by_invocation = selected if "selected" in locals() else {}
    for call in raw_calls:
        invocation = call.get("invocation")
        expected = expected_by_invocation.get(invocation)
        if expected is None:
            record.setdefault("errors", []).append(f"Unexpected optimizer invocation {invocation}")
            continue
        enriched = {**expected, **call}
        record["fit_calls"].append(enriched)
    expected_invocations = set(expected_by_invocation)
    observed_invocations = {call.get("invocation") for call in raw_calls}
    missing = sorted(expected_invocations - observed_invocations)
    if missing:
        record.setdefault("errors", []).append(f"Missing optimizer invocations: {missing}")
    if any(not call.get("success", False) for call in record["fit_calls"]):
        record["status"] = "failed"
    if record.get("errors"):
        record["status"] = "failed"
    return record


def worker(args: argparse.Namespace) -> int:
    manifest_path = args.manifest.resolve()
    manifest, scenarios = load_benchmark_manifest(manifest_path)
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    home_root = output_dir / "home"
    home_root.mkdir(parents=True, exist_ok=True)
    os.environ.update(isolated_environment(home_root, args.threads))

    run: dict[str, Any] = {
        "schema_version": 1,
        "branch": args.branch,
        "repetition": args.repetition,
        "warmup": args.warmup,
        "status": "failed",
        "metadata": benchmark_metadata(
            args.branch, args.examples_root, manifest_path, manifest, scenarios
        ),
        "notebooks": [],
    }
    all_passed = True
    examples_root = args.examples_root.resolve()
    notebooks = args.notebook or NOTEBOOKS
    for notebook_path in notebooks:
        source = examples_root / "pyglotaran_examples" / notebook_path
        notebook_record = execute_worker_notebook(
            source, output_dir, args.branch, manifest, notebook_path
        )
        run["notebooks"].append(notebook_record)
        if notebook_record["status"] != "passed":
            all_passed = False
    run["status"] = "passed" if all_passed else "failed"
    run["finished_at"] = datetime.now(timezone.utc).isoformat()
    (output_dir / "run.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    print(f"{args.branch} repetition={args.repetition} warmup={args.warmup}: {run['status']}")
    return 0 if all_passed else 1


def run_worker_process(
    python: Path,
    branch: str,
    examples_root: Path,
    manifest: Path,
    output_dir: Path,
    repetition: int,
    warmup: bool,
    threads: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(python),
        str(Path(__file__).resolve()),
        "worker",
        "--branch",
        branch,
        "--examples-root",
        str(examples_root.resolve()),
        "--manifest",
        str(manifest.resolve()),
        "--output",
        str(output_dir.resolve()),
        "--repetition",
        str(repetition),
        "--threads",
        str(threads),
    ]
    if warmup:
        command.append("--warmup")
    environment = isolated_environment(output_dir / "process-home", threads)
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    (output_dir / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if (output_dir / "run.json").is_file():
        run = json.loads((output_dir / "run.json").read_text(encoding="utf-8"))
    else:
        run = {"status": "failed", "branch": branch, "repetition": repetition, "warmup": warmup}
    run["process_returncode"] = completed.returncode
    return run


def run_benchmark(args: argparse.Namespace) -> int:
    manifest_path = args.manifest.resolve()
    manifest, _ = load_benchmark_manifest(manifest_path)
    output = args.output.resolve()
    if (output / "orchestration.json").exists():
        raise ValueError(f"Output already contains a completed benchmark: {output}")
    output.mkdir(parents=True, exist_ok=True)
    defaults = manifest["defaults"]
    repetitions = args.repetitions if args.repetitions is not None else defaults["repetitions"]
    warmups = args.warmups if args.warmups is not None else defaults["warmups"]
    if repetitions < 1 or warmups < 0:
        raise ValueError("repetitions must be positive and warmups must be non-negative")
    python_by_branch = {"main": args.main_python, "staging": args.staging_python}
    examples_by_branch = {"main": args.main_examples, "staging": args.staging_examples}
    schedule: list[dict[str, Any]] = []
    run_records: list[dict[str, Any]] = []

    for warmup_index in range(1, warmups + 1):
        for branch in ("main", "staging"):
            run_dir = output / "runs" / branch / f"warmup-{warmup_index:02d}"
            run = run_worker_process(
                python_by_branch[branch], branch, examples_by_branch[branch], manifest_path,
                run_dir, warmup_index, True, args.threads,
            )
            schedule.append({"branch": branch, "warmup": True, "repetition": warmup_index})
            run_records.append(run)

    for repetition in range(1, repetitions + 1):
        order = ("main", "staging") if repetition % 2 else ("staging", "main")
        for branch in order:
            run_dir = output / "runs" / branch / f"repetition-{repetition:02d}"
            run = run_worker_process(
                python_by_branch[branch], branch, examples_by_branch[branch], manifest_path,
                run_dir, repetition, False, args.threads,
            )
            schedule.append({"branch": branch, "warmup": False, "repetition": repetition})
            run_records.append(run)

    orchestration = {
        "schema_version": 1,
        "status": "passed" if all(run.get("status") == "passed" for run in run_records) else "failed",
        "manifest": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "repetitions": repetitions,
        "warmups": warmups,
        "threads": args.threads,
        "main_python": str(args.main_python.resolve()),
        "staging_python": str(args.staging_python.resolve()),
        "main_examples": str(args.main_examples.resolve()),
        "staging_examples": str(args.staging_examples.resolve()),
        "schedule": schedule,
        "runs": [
            {
                "branch": run.get("branch"),
                "repetition": run.get("repetition"),
                "warmup": run.get("warmup"),
                "status": run.get("status"),
                "process_returncode": run.get("process_returncode"),
            }
            for run in run_records
        ],
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    (output / "orchestration.json").write_text(json.dumps(orchestration, indent=2), encoding="utf-8")
    print(f"Benchmark orchestration: {orchestration['status']}")
    return 0 if orchestration["status"] == "passed" else 1


def raw_run_files(raw_root: Path) -> list[Path]:
    return sorted(path for path in raw_root.rglob("run.json") if path.is_file())


def collect_samples(
    raw_root: Path,
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    runs = [json.loads(path.read_text(encoding="utf-8")) for path in raw_run_files(raw_root)]
    timed_runs = [run for run in runs if not run.get("warmup", False)]
    samples: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    expected_repetitions = manifest["defaults"]["repetitions"]
    expected_warmups = manifest["defaults"]["warmups"]
    for branch in ("main", "staging"):
        warmup_runs = [run for run in runs if run.get("branch") == branch and run.get("warmup", False)]
        if len(warmup_runs) != expected_warmups:
            errors.append(
                {"branch": branch, "error": f"expected {expected_warmups} warm-up runs, found {len(warmup_runs)}"}
            )
        if any(run.get("status") != "passed" for run in warmup_runs):
            errors.append({"branch": branch, "error": "a warm-up run failed"})
        repetitions = {run.get("repetition") for run in timed_runs if run.get("branch") == branch}
        expected_set = set(range(1, expected_repetitions + 1))
        if repetitions != expected_set:
            errors.append(
                {"branch": branch, "error": f"expected timed repetitions {sorted(expected_set)}, found {sorted(repetitions)}"}
            )
    for run in timed_runs:
        for notebook in run.get("notebooks", []):
            for call in notebook.get("fit_calls", []):
                sample = {
                    **call,
                    "branch": run.get("branch"),
                    "repetition": run.get("repetition"),
                    "warmup": False,
                }
                samples.append(sample)
        if run.get("status") != "passed":
            errors.append({"run": run.get("branch"), "repetition": run.get("repetition"), "error": "run failed"})

    expected = {
        (case["id"], branch)
        for case in manifest["cases"]
        for branch in ("main", "staging")
    }
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for sample in samples:
        key = (sample.get("fit_id"), sample.get("branch"))
        by_key.setdefault(key, []).append(sample)
        if key not in expected:
            errors.append({"sample": key, "error": "unexpected fit ID or branch"})
        if not sample.get("success", False):
            errors.append({"sample": key, "error": sample.get("error", "fit failed")})
    for key in sorted(expected):
        count = len(by_key.get(key, []))
        if count != expected_repetitions:
            errors.append({"sample": key, "error": f"expected {expected_repetitions} timed samples, found {count}"})
    if errors:
        raise ValueError(json.dumps({"errors": errors}, indent=2))
    return samples, runs


def workload_values(samples: list[dict[str, Any]], field: str) -> dict[str, list[Any]]:
    values: dict[str, list[Any]] = {"main": [], "staging": []}
    for sample in samples:
        workload = sample.get("workload") or {}
        value = workload.get(field)
        if value is not None:
            values.setdefault(sample["branch"], []).append(value)
    return {branch: sorted({str(value) for value in branch_values}) for branch, branch_values in values.items()}


def aggregate_report(
    raw_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    samples, runs = collect_samples(raw_root, manifest)
    summaries: list[dict[str, Any]] = []
    for case in manifest["cases"]:
        branch_stats: dict[str, dict[str, Any]] = {}
        for branch in ("main", "staging"):
            durations = [
                float(sample["duration_seconds"])
                for sample in samples
                if sample["fit_id"] == case["id"] and sample["branch"] == branch
            ]
            branch_stats[branch] = {
                "n": len(durations),
                "mean_seconds": statistics.mean(durations),
                "std_seconds": statistics.stdev(durations) if len(durations) > 1 else 0.0,
                "min_seconds": min(durations),
                "median_seconds": statistics.median(durations),
                "max_seconds": max(durations),
            }
        main_mean = branch_stats["main"]["mean_seconds"]
        staging_mean = branch_stats["staging"]["mean_seconds"]
        nfev = workload_values(
            [sample for sample in samples if sample["fit_id"] == case["id"]],
            "number_of_function_evaluations",
        )
        warnings: list[str] = []
        workload_match: bool | None = None
        if nfev["main"] and nfev["staging"]:
            workload_match = nfev["main"] == nfev["staging"]
            if not workload_match:
                warnings.append(
                    "number_of_function_evaluations differs: "
                    f"main={nfev['main']}, staging={nfev['staging']}"
                )
        elif nfev["main"] or nfev["staging"]:
            workload_match = None
            warnings.append("number_of_function_evaluations is unavailable on one branch")
        summaries.append(
            {
                "id": case["id"],
                "scenario": case["scenario"],
                "notebook": case["notebook"],
                "main": branch_stats["main"],
                "staging": branch_stats["staging"],
                "delta_seconds": staging_mean - main_mean,
                "ratio_staging_over_main": staging_mean / main_mean if main_mean else None,
                "percent_change": ((staging_mean / main_mean) - 1) * 100 if main_mean else None,
                "workload_match": workload_match,
                "workload_function_evaluations": nfev,
                "warnings": warnings,
            }
        )
    return {
        "schema_version": 1,
        "status": "REPORT_ONLY",
        "measurement": {
            "timing": "public_fit_call",
            "warmups_excluded": manifest["defaults"]["warmups"],
            "timed_repetitions": manifest["defaults"]["repetitions"],
            "standard_deviation": "sample",
            "comparison_layer_used": False,
        },
        "raw_root": str(raw_root.resolve()),
        "manifest": str(manifest_path.resolve()),
        "manifest_sha256": sha256_file(manifest_path),
        "run_count": len(runs),
        "samples": samples,
        "summaries": summaries,
    }


def write_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "runtime.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (output_dir / "runtime.csv").open("w", newline="", encoding="utf-8") as stream:
        fieldnames = [
            "id", "scenario", "notebook", "main_mean_seconds", "main_std_seconds",
            "staging_mean_seconds", "staging_std_seconds", "delta_seconds",
            "ratio_staging_over_main", "percent_change", "workload_match", "warnings",
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for summary in report["summaries"]:
            writer.writerow(
                {
                    "id": summary["id"],
                    "scenario": summary["scenario"],
                    "notebook": summary["notebook"],
                    "main_mean_seconds": summary["main"]["mean_seconds"],
                    "main_std_seconds": summary["main"]["std_seconds"],
                    "staging_mean_seconds": summary["staging"]["mean_seconds"],
                    "staging_std_seconds": summary["staging"]["std_seconds"],
                    "delta_seconds": summary["delta_seconds"],
                    "ratio_staging_over_main": summary["ratio_staging_over_main"],
                    "percent_change": summary["percent_change"],
                    "workload_match": summary["workload_match"],
                    "warnings": "; ".join(summary["warnings"]),
                }
            )

    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    summaries = report["summaries"]
    labels = [summary["id"] for summary in summaries]
    positions = list(range(len(labels)))
    main_means = [summary["main"]["mean_seconds"] for summary in summaries]
    staging_means = [summary["staging"]["mean_seconds"] for summary in summaries]
    main_std = [summary["main"]["std_seconds"] for summary in summaries]
    staging_std = [summary["staging"]["std_seconds"] for summary in summaries]
    height = max(8.0, 0.42 * len(labels) + 2.0)
    figure, axis = plt.subplots(figsize=(15, height))
    offset = 0.18
    axis.barh(
        [position - offset for position in positions], main_means, height=0.32,
        xerr=main_std, label="v0.7.4", color="#4472c4", alpha=0.9, capsize=3,
    )
    axis.barh(
        [position + offset for position in positions], staging_means, height=0.32,
        xerr=staging_std, label="v0.8 staging", color="#ed7d31", alpha=0.9, capsize=3,
    )
    axis.set_yticks(positions, labels)
    axis.invert_yaxis()
    axis.set_xlabel("Fit runtime (seconds; mean ± sample standard deviation)")
    axis.set_title("Pinned pyglotaran fit-runtime comparison (5 timed runs; warm-up excluded)")
    axis.grid(axis="x", alpha=0.3)
    axis.legend()
    axis.margins(x=0.2)
    for position, summary in zip(positions, summaries):
        percent = summary["percent_change"]
        if percent is not None:
            maximum = max(summary["main"]["mean_seconds"], summary["staging"]["mean_seconds"])
            axis.text(maximum, position + 0.27, f"{percent:+.1f}%", va="center", fontsize=8)
    figure.tight_layout()
    figure.savefig(output_dir / "runtime.png", dpi=160)
    figure.savefig(output_dir / "runtime.svg")
    plt.close(figure)


def report_command(args: argparse.Namespace) -> int:
    manifest_path = args.manifest.resolve()
    manifest, _ = load_benchmark_manifest(manifest_path)
    report = aggregate_report(args.raw_root.resolve(), manifest_path, manifest)
    write_report(report, args.output.resolve())
    print(f"Wrote runtime report to {args.output.resolve()}")
    return 0


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description=__doc__)
    subparsers = command_parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run warm-ups and timed branch workers")
    run_parser.add_argument("--manifest", type=Path, default=ROOT / "validation" / "benchmarks.yml")
    run_parser.add_argument("--main-python", type=Path, required=True)
    run_parser.add_argument("--staging-python", type=Path, required=True)
    run_parser.add_argument("--main-examples", type=Path, required=True)
    run_parser.add_argument("--staging-examples", type=Path, required=True)
    run_parser.add_argument("--output", type=Path, required=True)
    run_parser.add_argument("--threads", type=int, default=1)
    run_parser.add_argument("--repetitions", type=int)
    run_parser.add_argument("--warmups", type=int)
    run_parser.set_defaults(function=run_benchmark)

    worker_parser = subparsers.add_parser("worker", help="Execute one branch in a fresh process")
    worker_parser.add_argument("--manifest", type=Path, required=True)
    worker_parser.add_argument("--branch", choices=("main", "staging"), required=True)
    worker_parser.add_argument("--examples-root", type=Path, required=True)
    worker_parser.add_argument("--output", type=Path, required=True)
    worker_parser.add_argument("--repetition", type=int, required=True)
    worker_parser.add_argument("--warmup", action="store_true")
    worker_parser.add_argument("--threads", type=int, default=1)
    worker_parser.add_argument("--notebook", action="append", help="Run only this notebook (repeatable)")
    worker_parser.set_defaults(function=worker)

    report_parser = subparsers.add_parser("report", help="Aggregate raw runs and create plots")
    report_parser.add_argument("--manifest", type=Path, default=ROOT / "validation" / "benchmarks.yml")
    report_parser.add_argument("--raw-root", type=Path, required=True)
    report_parser.add_argument("--output", type=Path, required=True)
    report_parser.set_defaults(function=report_command)
    return command_parser


def main() -> int:
    arguments = parser().parse_args()
    return arguments.function(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
