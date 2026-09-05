# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "jupyter-client>=8.6",
#   "matplotlib>=3.7,<4",
#   "nbclient>=0.10",
#   "nbformat>=5.10",
#   "psutil>=5.9",
# ]
# ///

"""Profile and compare one main notebook with one staging notebook."""

from __future__ import annotations

import argparse
import asyncio
import bisect
import csv
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
import traceback
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nbformat
import psutil
from jupyter_client import AsyncKernelManager
from jupyter_client.kernelspec import KernelSpec
from nbclient import NotebookClient


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAIN_PYTHON = ROOT / ".venv-main" / "Scripts" / "python.exe"
DEFAULT_STAGING_PYTHON = ROOT / ".venv-staging" / "Scripts" / "python.exe"
DEFAULT_OUTPUT = ROOT / "validation" / "benchmarks" / "memory-profile"
MIB = 1024**2


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clear_notebook(notebook: nbformat.NotebookNode) -> None:
    for cell in notebook.cells:
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None


def fit_probe_prelude(branch: str, record_path: Path) -> str:
    template = '''\
import functools
import importlib
import json
import time
from pathlib import Path

_fit_probe_path = Path(__RECORD_PATH__)
_fit_probe_records = []

def _fit_probe_value(result, name):
    for candidate in (
        result,
        getattr(result, "optimization_info", None),
        getattr(result, "optimization_result", None),
    ):
        if candidate is None:
            continue
        value = candidate.get(name) if isinstance(candidate, dict) else getattr(candidate, name, None)
        if value is not None and isinstance(value, (str, int, float, bool)):
            return value
    return None

def _fit_probe_write():
    _fit_probe_path.write_text(json.dumps(_fit_probe_records, indent=2), encoding="utf-8")

def _fit_probe_invoke(original, entrypoint, args, kwargs):
    record = {
        "entrypoint": entrypoint,
        "dry_run": kwargs.get("dry_run"),
        "success": False,
    }
    started = time.perf_counter_ns()
    try:
        result = original(*args, **kwargs)
    except BaseException as error:
        finished = time.perf_counter_ns()
        record.update(
            {
                "duration_seconds": (finished - started) / 1_000_000_000,
                "error": repr(error),
            }
        )
        _fit_probe_records.append(record)
        _fit_probe_write()
        raise
    finished = time.perf_counter_ns()
    record.update(
        {
            "duration_seconds": (finished - started) / 1_000_000_000,
            "success": True,
            "number_of_function_evaluations": _fit_probe_value(
                result, "number_of_function_evaluations"
            ),
            "number_of_jacobian_evaluations": _fit_probe_value(
                result, "number_of_jacobian_evaluations"
            ),
            "number_of_free_parameters": _fit_probe_value(result, "number_of_free_parameters"),
            "error": None,
        }
    )
    _fit_probe_records.append(record)
    _fit_probe_write()
    return result

if __BRANCH__ == "main":
    _fit_probe_module = importlib.import_module("glotaran.optimization.optimize")
    _fit_probe_original = _fit_probe_module.optimize

    @functools.wraps(_fit_probe_original)
    def _fit_probe_timed(*args, **kwargs):
        return _fit_probe_invoke(
            _fit_probe_original,
            "glotaran.optimization.optimize.optimize",
            args,
            kwargs,
        )

    _fit_probe_module.optimize = _fit_probe_timed
else:
    _fit_probe_module = importlib.import_module("glotaran.project.scheme")
    _fit_probe_class = _fit_probe_module.Scheme
    _fit_probe_original = _fit_probe_class.optimize

    @functools.wraps(_fit_probe_original)
    def _fit_probe_timed(self, *args, **kwargs):
        return _fit_probe_invoke(
            _fit_probe_original,
            "glotaran.project.scheme.Scheme.optimize",
            (self, *args),
            kwargs,
        )

    _fit_probe_class.optimize = _fit_probe_timed

'''
    return template.replace("__RECORD_PATH__", repr(str(record_path))).replace(
        "__BRANCH__", repr(branch)
    )


def home_environment(home_root: Path) -> dict[str, str]:
    home_root.mkdir(parents=True, exist_ok=True)
    drive, path = os.path.splitdrive(str(home_root))
    return {
        "HOME": str(home_root),
        "USERPROFILE": str(home_root),
        "HOMEDRIVE": drive,
        "HOMEPATH": path,
        "MPLBACKEND": "Agg",
    }


def explicit_kernel_manager(target_python: Path, environment: dict[str, str]) -> AsyncKernelManager:
    spec = KernelSpec()
    spec.argv = [str(target_python), "-m", "ipykernel_launcher", "-f", "{connection_file}"]
    spec.display_name = f"memory-profile ({target_python.parent.parent.name})"
    spec.language = "python"
    spec.env = environment
    manager = AsyncKernelManager(kernel_name="python3")
    manager._kernel_spec = spec
    return manager


def process_tree_memory(pid: int) -> dict[str, int] | None:
    try:
        root = psutil.Process(pid)
        processes = [root, *root.children(recursive=True)]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None

    seen: set[int] = set()
    root_rss = 0
    total_rss = 0
    process_count = 0
    for process in processes:
        if process.pid in seen:
            continue
        seen.add(process.pid)
        try:
            rss = process.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        total_rss += rss
        process_count += 1
        if process.pid == pid:
            root_rss = rss
    return {
        "rss_bytes": total_rss,
        "root_rss_bytes": root_rss,
        "children_rss_bytes": total_rss - root_rss,
        "process_count": process_count,
    }


def monitor_process(process: subprocess.Popen[bytes], interval_seconds: float) -> list[dict[str, float | int]]:
    started = time.perf_counter()
    next_sample = started
    samples: list[dict[str, float | int]] = []
    while True:
        memory = process_tree_memory(process.pid)
        if memory is not None:
            samples.append({"elapsed_s": time.perf_counter() - started, **memory})
        if process.poll() is not None:
            break
        next_sample += interval_seconds
        delay = next_sample - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
    process.wait()
    return samples


def write_samples(path: Path, samples: list[dict[str, float | int]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "elapsed_s",
                "rss_bytes",
                "root_rss_bytes",
                "children_rss_bytes",
                "process_count",
            ],
        )
        writer.writeheader()
        writer.writerows(samples)


def read_samples(path: Path) -> list[dict[str, float | int]]:
    samples: list[dict[str, float | int]] = []
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            samples.append(
                {
                    "elapsed_s": float(row["elapsed_s"]),
                    "rss_bytes": int(row["rss_bytes"]),
                    "root_rss_bytes": int(row["root_rss_bytes"]),
                    "children_rss_bytes": int(row["children_rss_bytes"]),
                    "process_count": int(row["process_count"]),
                }
            )
    return samples


def worker(arguments: argparse.Namespace) -> int:
    run_output = arguments.run_output.resolve()
    run_output.mkdir(parents=True, exist_ok=True)
    source = arguments.notebook.resolve()
    target_python = arguments.target_python.resolve()
    record: dict[str, Any] = {
        "branch": arguments.branch,
        "repetition": arguments.repetition,
        "source": str(source),
        "source_sha256": sha256_file(source) if source.is_file() else None,
        "target_python": str(target_python),
        "worker_python": sys.executable,
        "stop_after_cell": arguments.stop_after_cell,
        "record_fit_calls": arguments.record_fit_calls,
        "started_at": utc_now(),
        "status": "failed",
    }
    manager: AsyncKernelManager | None = None
    try:
        if not source.is_file():
            raise FileNotFoundError(source)
        if not target_python.is_file():
            raise FileNotFoundError(target_python)
        if platform.system() == "Windows":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                selector_policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
                if selector_policy is not None:
                    asyncio.set_event_loop_policy(selector_policy())
        home = home_environment(run_output / "home")
        os.environ.update(home)
        with source.open(encoding="utf-8") as stream:
            notebook = nbformat.read(stream, as_version=4)
        clear_notebook(notebook)
        if arguments.stop_after_cell is not None:
            notebook.cells = notebook.cells[: arguments.stop_after_cell + 1]
        if arguments.record_fit_calls:
            notebook.cells.insert(
                0,
                nbformat.v4.new_code_cell(
                    source=fit_probe_prelude(arguments.branch, run_output / "fit-calls.json")
                ),
            )
        manager = explicit_kernel_manager(target_python, home)
        client = NotebookClient(
            notebook,
            km=manager,
            timeout=None,
            resources={"metadata": {"path": str(source.parent)}},
        )
        started = time.perf_counter()
        client.execute()
        record["duration_s"] = time.perf_counter() - started
        record["status"] = "passed"
    except Exception as error:  # noqa: BLE001 - retain the notebook traceback in the run record
        record["error"] = repr(error)
        record["traceback"] = traceback.format_exc()
    finally:
        if manager is not None:
            try:
                async def shutdown_manager() -> None:
                    if await manager.is_alive():
                        await manager.shutdown_kernel(now=True)

                asyncio.run(shutdown_manager())
            except Exception:  # noqa: BLE001 - cleanup must not hide the execution error
                pass
        record["finished_at"] = utc_now()
        (run_output / "run.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return 0 if record["status"] == "passed" else 1


def run_worker(
    *,
    branch: str,
    repetition: int,
    notebook: Path,
    target_python: Path,
    run_output: Path,
    interval_seconds: float,
    stop_after_cell: int | None,
    record_fit_calls: bool,
) -> dict[str, Any]:
    run_output.mkdir(parents=True, exist_ok=True)
    stdout_path = run_output / "stdout.txt"
    stderr_path = run_output / "stderr.txt"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--branch",
        branch,
        "--repetition",
        str(repetition),
        "--notebook",
        str(notebook.resolve()),
        "--target-python",
        str(target_python.resolve()),
        "--run-output",
        str(run_output.resolve()),
    ]
    if stop_after_cell is not None:
        command.extend(["--stop-after-cell", str(stop_after_cell)])
    if record_fit_calls:
        command.append("--record-fit-calls")
    environment = os.environ.copy()
    environment["MPLBACKEND"] = "Agg"
    environment["PYTHONUNBUFFERED"] = "1"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=environment,
            stdout=stdout,
            stderr=stderr,
        )
        samples = monitor_process(process, interval_seconds)
    samples_path = run_output / "samples.csv"
    write_samples(samples_path, samples)
    if (run_output / "run.json").is_file():
        record = json.loads((run_output / "run.json").read_text(encoding="utf-8"))
    else:
        record = {"status": "failed", "error": "Worker did not write run.json"}
    duration = float(record.get("duration_s", samples[-1]["elapsed_s"] if samples else 0.0))
    rss_values = [int(sample["rss_bytes"]) for sample in samples]
    record.update(
        {
            "process_returncode": process.returncode,
            "sample_interval_s": interval_seconds,
            "sample_count": len(samples),
            "monitor_duration_s": float(samples[-1]["elapsed_s"]) if samples else 0.0,
            "duration_s": duration,
            "peak_rss_bytes": max(rss_values) if rss_values else None,
            "mean_rss_bytes": statistics.fmean(rss_values) if rss_values else None,
            "samples_file": str(samples_path),
        }
    )
    fit_calls_path = run_output / "fit-calls.json"
    if fit_calls_path.is_file():
        record["fit_calls_file"] = str(fit_calls_path)
        record["fit_calls"] = json.loads(fit_calls_path.read_text(encoding="utf-8"))
    (run_output / "run.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def interpolated_value(
    times: list[float], values: list[float], target: float
) -> float | None:
    if not times or target < times[0] or target > times[-1]:
        return None
    right = bisect.bisect_right(times, target)
    if right == 0:
        return values[0]
    if right == len(times):
        return values[-1]
    left = right - 1
    span = times[right] - times[left]
    if span <= 0:
        return values[right]
    fraction = (target - times[left]) / span
    return values[left] + fraction * (values[right] - values[left])


def average_trace(
    runs: list[dict[str, Any]], interval_seconds: float, time_limit: float
) -> tuple[list[float], list[float]]:
    if not runs:
        return [], []
    steps = int(math.floor(time_limit / interval_seconds)) + 1
    times: list[float] = []
    values: list[float] = []
    loaded = [(read_samples(Path(run["samples_file"])), run) for run in runs]
    prepared = [
        (
            [float(sample["elapsed_s"]) for sample in samples],
            [float(sample["rss_bytes"]) / MIB for sample in samples],
        )
        for samples, _ in loaded
    ]
    for index in range(steps):
        target = index * interval_seconds
        current = [
            value
            for sample_times, sample_values in prepared
            if (value := interpolated_value(sample_times, sample_values, target)) is not None
        ]
        if current:
            times.append(target)
            values.append(statistics.fmean(current))
    return times, values


def branch_stats(runs: list[dict[str, Any]]) -> dict[str, float | int | None]:
    durations = [float(run["duration_s"]) for run in runs]
    peaks = [int(run["peak_rss_bytes"]) for run in runs if run.get("peak_rss_bytes") is not None]
    means = [int(run["mean_rss_bytes"]) for run in runs if run.get("mean_rss_bytes") is not None]
    return {
        "runs": len(runs),
        "average_duration_s": statistics.fmean(durations) if durations else None,
        "median_duration_s": statistics.median(durations) if durations else None,
        "longest_duration_s": max(durations) if durations else None,
        "average_peak_rss_bytes": statistics.fmean(peaks) if peaks else None,
        "maximum_peak_rss_bytes": max(peaks) if peaks else None,
        "average_sampled_rss_bytes": statistics.fmean(means) if means else None,
    }


def plot_branch(
    output: Path,
    branch: str,
    runs: list[dict[str, Any]],
    interval_seconds: float,
    time_limit: float,
) -> list[str]:
    figure, axis = plt.subplots(figsize=(13, 6.5))
    notebook_name = Path(str(runs[0]["source"])).name if runs else "notebook"
    for index, run in enumerate(runs, start=1):
        samples = read_samples(Path(run["samples_file"]))
        axis.plot(
            [float(sample["elapsed_s"]) for sample in samples],
            [float(sample["rss_bytes"]) / MIB for sample in samples],
            linewidth=0.9,
            alpha=0.55,
            label=f"trace {index}",
        )
    mean_times, mean_values = average_trace(runs, interval_seconds, time_limit)
    if mean_times:
        axis.plot(mean_times, mean_values, color="black", linewidth=2.4, label="average")
    stats = branch_stats(runs)
    axis.set_title(f"{branch}: {notebook_name} memory profile ({len(runs)} traces)")
    axis.set_xlabel("Elapsed execution time (s)")
    axis.set_ylabel("Process-tree RSS (MiB)")
    axis.set_xlim(0, time_limit)
    axis.grid(True, alpha=0.25)
    axis.legend(ncol=3, loc="upper left")
    axis.text(
        0.995,
        0.98,
        "Average runtime: "
        f"{stats['average_duration_s']:.2f} s\n"
        f"Average peak RSS: {float(stats['average_peak_rss_bytes']) / MIB:.1f} MiB\n"
        f"Maximum peak RSS: {float(stats['maximum_peak_rss_bytes']) / MIB:.1f} MiB",
        transform=axis.transAxes,
        ha="right",
        va="top",
        bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "0.75"},
    )
    figure.tight_layout()
    paths = [output / f"{branch}-memory.png", output / f"{branch}-memory.svg"]
    for path in paths:
        figure.savefig(path, dpi=160 if path.suffix == ".png" else None)
    plt.close(figure)
    return [str(path) for path in paths]


def plot_comparison(
    output: Path,
    runs_by_branch: dict[str, list[dict[str, Any]]],
    interval_seconds: float,
    time_limit: float,
) -> list[str]:
    figure, axes = plt.subplots(2, 1, sharex=True, figsize=(13, 10), constrained_layout=True)
    colors = {"main": "#1769aa", "staging": "#c44e52"}
    for axis, branch in zip(axes, ("main", "staging")):
        runs = runs_by_branch[branch]
        notebook_name = Path(str(runs[0]["source"])).name if runs else "notebook"
        for index, run in enumerate(runs, start=1):
            samples = read_samples(Path(run["samples_file"]))
            axis.plot(
                [float(sample["elapsed_s"]) for sample in samples],
                [float(sample["rss_bytes"]) / MIB for sample in samples],
                linewidth=0.85,
                alpha=0.42,
                label=f"trace {index}",
            )
        mean_times, mean_values = average_trace(runs, interval_seconds, time_limit)
        if mean_times:
            axis.plot(
                mean_times,
                mean_values,
                color=colors[branch],
                linewidth=2.5,
                label="average",
            )
        stats = branch_stats(runs)
        axis.set_title(f"{branch}: {notebook_name} ({len(runs)} traces)", loc="left")
        axis.set_ylabel("RSS (MiB)")
        axis.set_xlim(0, time_limit)
        axis.grid(True, alpha=0.25)
        axis.legend(ncol=3, loc="upper left")
        if stats["average_duration_s"] is not None:
            axis.text(
                0.995,
                0.98,
                f"Average runtime: {stats['average_duration_s']:.2f} s\n"
                f"Average peak RSS: {float(stats['average_peak_rss_bytes']) / MIB:.1f} MiB",
                transform=axis.transAxes,
                ha="right",
                va="top",
                bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "0.75"},
            )
    axes[-1].set_xlabel("Elapsed execution time (s)")
    figure.suptitle(f"Notebook memory comparison (shared axis, 0-{time_limit:.0f} s)")
    paths = [output / "comparison-memory.png", output / "comparison-memory.svg"]
    for path in paths:
        figure.savefig(path, dpi=160 if path.suffix == ".png" else None)
    plt.close(figure)
    return [str(path) for path in paths]


def write_summary_csv(output: Path, runs_by_branch: dict[str, list[dict[str, Any]]]) -> None:
    with (output / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        fieldnames = [
            "branch",
            "repetition",
            "status",
            "duration_s",
            "sample_count",
            "peak_rss_mib",
            "mean_rss_mib",
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for branch, runs in runs_by_branch.items():
            for run in runs:
                writer.writerow(
                    {
                        "branch": branch,
                        "repetition": run.get("repetition"),
                        "status": run.get("status"),
                        "duration_s": run.get("duration_s"),
                        "sample_count": run.get("sample_count"),
                        "peak_rss_mib": (
                            float(run["peak_rss_bytes"]) / MIB
                            if run.get("peak_rss_bytes") is not None
                            else None
                        ),
                        "mean_rss_mib": (
                            float(run["mean_rss_bytes"]) / MIB
                            if run.get("mean_rss_bytes") is not None
                            else None
                        ),
                    }
                )


def run_profile(arguments: argparse.Namespace) -> int:
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    interval_seconds = arguments.interval_ms / 1000
    branches = {
        "main": (arguments.main_notebook.resolve(), arguments.main_python.resolve()),
        "staging": (arguments.staging_notebook.resolve(), arguments.staging_python.resolve()),
    }
    for branch, (notebook, target_python) in branches.items():
        if not notebook.is_file():
            raise FileNotFoundError(notebook)
        if not target_python.is_file():
            raise FileNotFoundError(target_python)

    started_at = utc_now()
    runs_by_branch: dict[str, list[dict[str, Any]]] = {"main": [], "staging": []}
    for branch, (notebook, target_python) in branches.items():
        for repetition in range(1, arguments.runs + 1):
            run_output = output / "runs" / branch / f"run-{repetition:02d}"
            print(f"Running {branch} trace {repetition}/{arguments.runs} ...", flush=True)
            record = run_worker(
                branch=branch,
                repetition=repetition,
                notebook=notebook,
                target_python=target_python,
                run_output=run_output,
                interval_seconds=interval_seconds,
                stop_after_cell=arguments.stop_after_cell,
                record_fit_calls=arguments.record_fit_calls,
            )
            runs_by_branch[branch].append(record)
            print(
                f"  {record.get('status')} in {float(record.get('duration_s', 0.0)):.2f} s, "
                f"peak {float(record.get('peak_rss_bytes') or 0) / MIB:.1f} MiB, "
                f"{record.get('sample_count', 0)} samples",
                flush=True,
            )

    successful_runs = [
        run
        for runs in runs_by_branch.values()
        for run in runs
        if run.get("status") == "passed" and run.get("samples_file")
    ]
    if not successful_runs:
        raise RuntimeError("No notebook executions completed successfully")
    longest_execution = max(float(run["duration_s"]) for run in successful_runs)
    time_limit = max(10.0, math.ceil(longest_execution / 10.0) * 10.0)
    plots: list[str] = []
    for branch, runs in runs_by_branch.items():
        successful = [run for run in runs if run.get("status") == "passed" and run.get("samples_file")]
        if successful:
            plots.extend(plot_branch(output, branch, successful, interval_seconds, time_limit))
    plots.extend(
        plot_comparison(
            output,
            {
                branch: [
                    run
                    for run in runs
                    if run.get("status") == "passed" and run.get("samples_file")
                ]
                for branch, runs in runs_by_branch.items()
            },
            interval_seconds,
            time_limit,
        )
    )
    write_summary_csv(output, runs_by_branch)
    manifest = {
        "schema_version": 1,
        "started_at": started_at,
        "finished_at": utc_now(),
        "python": sys.version,
        "worker_python": sys.executable,
        "platform": platform.platform(),
        "sample_interval_ms": arguments.interval_ms,
        "requested_runs": arguments.runs,
        "stop_after_cell": arguments.stop_after_cell,
        "record_fit_calls": arguments.record_fit_calls,
        "comparison_time_limit_s": time_limit,
        "longest_successful_execution_s": longest_execution,
        "branches": {
            branch: {
                "notebook": str(notebook),
                "notebook_sha256": sha256_file(notebook),
                "target_python": str(target_python),
                "statistics": branch_stats(
                    [
                        run
                        for run in runs_by_branch[branch]
                        if run.get("status") == "passed" and run.get("samples_file")
                    ]
                ),
            }
            for branch, (notebook, target_python) in branches.items()
        },
        "plots": plots,
        "runs": runs_by_branch,
    }
    (output / "memory-profile.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    failed = [run for runs in runs_by_branch.values() for run in runs if run.get("status") != "passed"]
    print(f"Comparison axis: 0-{time_limit:.0f} s; plots written to {output}")
    return 1 if failed else 0


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--main-notebook",
        type=Path,
        help="Notebook to execute with the main environment.",
    )
    parser.add_argument(
        "--staging-notebook",
        type=Path,
        help="Notebook to execute with the staging environment.",
    )
    parser.add_argument("--main-python", type=Path, default=DEFAULT_MAIN_PYTHON)
    parser.add_argument("--staging-python", type=Path, default=DEFAULT_STAGING_PYTHON)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=positive_int, default=5)
    parser.add_argument("--interval-ms", type=positive_float, default=50.0)
    parser.add_argument(
        "--stop-after-cell",
        type=nonnegative_int,
        help="Execute through this zero-based original notebook cell.",
    )
    parser.add_argument(
        "--record-fit-calls",
        action="store_true",
        help="Record public optimizer call timing and evaluation metadata.",
    )
    parser.add_argument("--branch", choices=("main", "staging"), help=argparse.SUPPRESS)
    parser.add_argument("--repetition", type=positive_int, help=argparse.SUPPRESS)
    parser.add_argument("--notebook", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--target-python", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--run-output", type=Path, help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if not arguments.worker:
        missing = [
            option
            for option, value in (
                ("--main-notebook", arguments.main_notebook),
                ("--staging-notebook", arguments.staging_notebook),
            )
            if value is None
        ]
        if missing:
            parser.error(f"missing required option(s): {', '.join(missing)}")
    if arguments.worker and (
        arguments.branch is None
        or arguments.repetition is None
        or arguments.notebook is None
        or arguments.target_python is None
        or arguments.run_output is None
    ):
        parser.error("worker arguments are incomplete")
    return arguments


def main() -> int:
    arguments = parse_arguments()
    if arguments.worker:
        return worker(arguments)
    return run_profile(arguments)


if __name__ == "__main__":
    raise SystemExit(main())