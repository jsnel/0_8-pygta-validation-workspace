"""Run the pinned pyglotaran-examples notebooks into an isolated output tree.

This deliberately does not use ``scripts/run_examples_notebooks.py`` directly: that
script executes notebooks in place and its ``run-all`` command does not return a
non-zero exit code when one example fails. The examples repository remains an
unmodified source checkout; callers should pass a copy as ``--examples-root``.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import traceback
from datetime import datetime
from datetime import timezone
from pathlib import Path

import nbformat
from nbclient import NotebookClient


NOTEBOOKS = (
    "study_fluorescence/fluorescence_global_and_target_analysis.ipynb",
    "study_transient_absorption/transient_absorption_target_analysis.ipynb",
    "study_transient_absorption/transient_absorption_two_dataset_analysis.ipynb",
    "ex_spectral_constraints/ex_spectral_constraints.ipynb",
    "ex_spectral_guidance/ex_spectral_guidance.ipynb",
    "ex_two_datasets/ex_two_datasets.ipynb",
    "test/simultaneous_analysis_3d_disp/sim_analysis_script_3d_disp.ipynb",
    "test/simultaneous_analysis_3d_nodisp/simultaneous_analysis_3d_nodisp.ipynb",
    "test/simultaneous_analysis_3d_weight/simultaneous_analysis_3d_weight.ipynb",
    "test/simultaneous_analysis_6d_disp/simultaneous_analysis_6d_disp.ipynb",
    "ex_doas_beta/ex_doas_beta.ipynb",
)


def git_revision(path: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def tree_sha256(root: Path) -> str:
    """Hash a source tree deterministically for snapshots without git history."""

    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root).as_posix().encode()
        digest.update(relative)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def installed_source_manifests() -> dict[str, object]:
    manifests: dict[str, object] = {}
    for import_name, manifest_name in (("glotaran", "pyglotaran"), ("pyglotaran_extras", "pyglotaran_extras")):
        try:
            module = importlib.import_module(import_name)
            source_root = Path(module.__file__).resolve().parent
            project_root = next(
                (candidate for candidate in (source_root, *source_root.parents) if (candidate / "uv.lock").is_file()),
                source_root,
            )
            manifests[manifest_name] = {
                "source_root": str(source_root),
                "source_tree_sha256": tree_sha256(source_root),
                "lockfile": str(project_root / "uv.lock"),
                "lockfile_sha256": file_sha256(project_root / "uv.lock"),
            }
        except (ImportError, AttributeError):
            manifests[manifest_name] = None
    return manifests


def compress_results(results_root: Path) -> None:
    """Apply the same NetCDF compression used by the upstream examples runner."""
    import xarray as xr

    for data_file in results_root.rglob("*.nc"):
        dataset = xr.load_dataset(data_file)
        encoding = {variable: {"zlib": True, "complevel": 5} for variable in dataset.data_vars}
        dataset.to_netcdf(data_file, encoding=encoding)


def run_notebooks(examples_root: Path, output_root: Path, label: str) -> int:
    examples_root = examples_root.resolve()
    output_root = output_root.resolve()
    notebooks_root = output_root / "notebooks"
    home_root = output_root / "home"
    result_root = home_root / "pyglotaran_examples_results"
    notebooks_root.mkdir(parents=True, exist_ok=True)
    home_root.mkdir(parents=True, exist_ok=True)

    # The upstream runner uses Path.home() for its results. Set the Windows home
    # variables before any notebook code runs so the two baselines cannot collide.
    environment = os.environ.copy()
    environment["USERPROFILE"] = str(home_root)
    environment["HOME"] = str(home_root)
    drive, path = os.path.splitdrive(str(home_root))
    environment["HOMEDRIVE"] = drive
    environment["HOMEPATH"] = path
    environment.setdefault("MPLBACKEND", "Agg")
    os.environ.update(environment)

    manifest: dict[str, object] = {
        "label": label,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "examples_root": str(examples_root),
        "examples_revision": git_revision(examples_root),
        "examples_tree_sha256": tree_sha256(examples_root),
        "pyglotaran": package_version("pyglotaran"),
        "pyglotaran_extras": package_version("pyglotaran-extras"),
        "installed_source_manifests": installed_source_manifests(),
        "notebooks": [],
        "results_root": [],
    }

    failures = 0
    for relative_path in NOTEBOOKS:
        source = examples_root / "pyglotaran_examples" / relative_path
        output = notebooks_root / relative_path
        output.parent.mkdir(parents=True, exist_ok=True)
        record: dict[str, object] = {"path": relative_path, "source": str(source)}
        print(f"RUNNING {label}: {relative_path}", flush=True)
        if not source.is_file():
            record.update({"status": "missing", "error": f"Missing notebook: {source}"})
            failures += 1
        else:
            try:
                with source.open(encoding="utf-8") as notebook_file:
                    notebook = nbformat.read(notebook_file, as_version=4)
                NotebookClient(
                    notebook,
                    timeout=None,
                    kernel_name="python3",
                    resources={"metadata": {"path": str(source.parent)}},
                ).execute()
                with output.open("w", encoding="utf-8") as notebook_file:
                    nbformat.write(notebook, notebook_file)
                record["status"] = "passed"
            except Exception as error:  # noqa: BLE001 - preserve notebook traceback in manifest
                record.update(
                    {
                        "status": "failed",
                        "error": repr(error),
                        "traceback": traceback.format_exc(),
                    }
                )
                failures += 1
        manifest["notebooks"].append(record)  # type: ignore[union-attr]

    result_roots = sorted(
        path
        for path in home_root.iterdir()
        if path.is_dir() and path.name.startswith("pyglotaran_examples_results")
    )
    for result_root in result_roots:
        compress_results(result_root)
    manifest["results_root"] = [str(path) for path in result_roots]
    manifest["results_tree_sha256"] = {
        str(path): tree_sha256(path) for path in result_roots
    }
    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    manifest["failures"] = failures
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Completed {label}: {len(NOTEBOOKS) - failures}/{len(NOTEBOOKS)} passed")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--label", required=True)
    arguments = parser.parse_args()
    return run_notebooks(arguments.examples_root, arguments.output_root, arguments.label)


if __name__ == "__main__":
    raise SystemExit(main())
