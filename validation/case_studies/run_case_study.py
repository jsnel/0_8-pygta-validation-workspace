"""Execute case-study notebooks in an isolated copy and package evidence."""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import traceback
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

import nbformat
from nbclient import NotebookClient


IMAGE_MIME_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/svg+xml": ".svg",
}
FILE_PLOT_SUFFIXES = {".png", ".jpg", ".jpeg", ".svg", ".pdf", ".tif", ".tiff"}
RESULT_SUFFIXES = {".nc", ".yml", ".yaml", ".csv"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_map(root: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts:
            result[path.relative_to(root).as_posix()] = {
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
    return result


def tree_sha256(files: dict[str, dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, metadata in sorted(files.items()):
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(metadata["sha256"].encode())
        digest.update(b"\0")
    return digest.hexdigest()


def git(path: Path, *arguments: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), *arguments],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def source_patch(root: Path, base_revision: str) -> str:
    tracked = subprocess.run(
        ["git", "-C", str(root), "diff", "--binary", base_revision],
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode != 0:
        raise RuntimeError(f"Unable to create tracked source patch: {tracked.stderr}")
    parts = [tracked.stdout]
    untracked = (git(root, "ls-files", "--others", "--exclude-standard") or "").splitlines()
    for relative in untracked:
        addition = subprocess.run(
            ["git", "-C", str(root), "diff", "--binary", "--no-index", "--", "/dev/null", relative],
            capture_output=True,
            text=True,
            check=False,
        )
        if addition.returncode not in {0, 1}:
            raise RuntimeError(f"Unable to include untracked file {relative}: {addition.stderr}")
        parts.append(addition.stdout)
    return "".join(parts)


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def extract_logs(notebook: Any) -> tuple[str, str]:
    stdout: list[str] = []
    stderr: list[str] = []
    for cell in notebook.cells:
        for output in cell.get("outputs", []):
            if output.get("output_type") == "stream":
                target = stderr if output.get("name") == "stderr" else stdout
                target.append(output.get("text", ""))
            elif output.get("output_type") == "error":
                stderr.append("\n".join(output.get("traceback", [])))
    return "".join(stdout), "\n".join(stderr)


def extract_inline_images(notebook: Any, output_dir: Path) -> list[dict[str, Any]]:
    records = []
    for cell_index, cell in enumerate(notebook.cells):
        for output_index, output in enumerate(cell.get("outputs", [])):
            data = output.get("data", {})
            for mime_type, suffix in IMAGE_MIME_TYPES.items():
                if mime_type not in data:
                    continue
                path = output_dir / f"cell-{cell_index:04d}-output-{output_index:03d}{suffix}"
                path.parent.mkdir(parents=True, exist_ok=True)
                value = data[mime_type]
                if isinstance(value, list):
                    value = "".join(value)
                if mime_type == "image/svg+xml":
                    path.write_text(value, encoding="utf-8")
                else:
                    path.write_bytes(base64.b64decode(value))
                records.append(
                    {
                        "path": str(path),
                        "mime_type": mime_type,
                        "cell_index": cell_index,
                        "output_index": output_index,
                        "sha256": sha256(path),
                    }
                )
    return records


def environment_metadata() -> dict[str, Any]:
    freeze = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"],
        capture_output=True,
        text=True,
        check=False,
    )
    package_list = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--format=json"],
        capture_output=True,
        text=True,
        check=False,
    )
    relevant_environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper()
        in {
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
            "BLIS_NUM_THREADS",
            "MPLBACKEND",
        }
    }
    return {
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "pyglotaran": package_version("pyglotaran"),
        "pyglotaran_extras": package_version("pyglotaran-extras"),
        "nbclient": package_version("nbclient"),
        "nbformat": package_version("nbformat"),
        "pip_freeze_exit_code": freeze.returncode,
        "pip_freeze": freeze.stdout.splitlines(),
        "pip_freeze_stderr": freeze.stderr.splitlines(),
        "pip_list_exit_code": package_list.returncode,
        "pip_list": json.loads(package_list.stdout) if package_list.returncode == 0 else [],
        "pip_list_stderr": package_list.stderr.splitlines(),
        "thread_and_plot_environment": relevant_environment,
    }


def instrument_fit_results(notebook: Any) -> list[dict[str, str]]:
    """Save every real fit result without modifying the source notebook on disk."""
    captures: list[dict[str, str]] = []
    notebook.cells.insert(
        0,
        nbformat.v4.new_code_cell(
            "\n".join(
                [
                    "from glotaran.io import SAVING_OPTIONS_DEFAULT as _case_study_default_saving_options",
                    "from glotaran.io import save_result as _case_study_save_result",
                    "if isinstance(_case_study_default_saving_options, dict):",
                    "    _case_study_capture_saving_options = dict(_case_study_default_saving_options)",
                    "    _case_study_capture_saving_options['data_filter'] = set()",
                    "else:",
                    "    from glotaran.io.interface import SavingOptions as _CaseStudySavingOptions",
                    "    _case_study_capture_saving_options = _CaseStudySavingOptions(data_filter=None, report=False)",
                ]
            )
        ),
    )
    for cell in notebook.cells[1:]:
        if cell.cell_type != "code":
            continue
        tree = ast.parse(cell.source or "pass")
        statements = []
        for node in tree.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            if not isinstance(node.targets[0], ast.Name) or not isinstance(node.value, ast.Call):
                continue
            function = node.value.func
            is_optimize = (
                isinstance(function, ast.Name)
                and function.id == "optimize"
                or isinstance(function, ast.Attribute)
                and function.attr == "optimize"
            )
            if not is_optimize:
                continue
            if any(
                keyword.arg == "dry_run"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in node.value.keywords
            ):
                continue
            target = node.targets[0].id
            index = len(captures) + 1
            capture_label = target.removesuffix("_native")
            relative = f"case-study-results/fit-{index:03d}-{capture_label}/result.yaml"
            captures.append({"variable": target, "result_path": relative})
            statements.append(
                f"_case_study_save_result(result={target}, result_path={relative!r}, "
                "allow_overwrite=True, saving_options=_case_study_capture_saving_options)"
            )
        if statements:
            cell.source = f"{cell.source.rstrip()}\n\n" + "\n".join(statements)
    return captures


def execute_notebook(
    source: Path,
    executed: Path,
    inline_root: Path,
    stdout_path: Path,
    stderr_path: Path,
    capture_fit_results: bool = False,
) -> dict[str, Any]:
    started = now()
    notebook = nbformat.read(source, as_version=4)
    captured_fit_results = instrument_fit_results(notebook) if capture_fit_results else []
    error = None
    try:
        NotebookClient(
            notebook,
            timeout=None,
            kernel_name="python3",
            resources={"metadata": {"path": str(source.parent)}},
        ).execute()
        status = "PASSED"
    except Exception as exception:  # noqa: BLE001 - package complete execution evidence
        status = "FAILED"
        error = {"exception": repr(exception), "traceback": traceback.format_exc()}
    executed.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, executed)
    stdout, stderr = extract_logs(notebook)
    if error:
        stderr = f"{stderr}\n{error['traceback']}"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    inline_images = extract_inline_images(notebook, inline_root)
    return {
        "status": status,
        "started_at": started,
        "finished_at": now(),
        "source": str(source),
        "executed_notebook": str(executed),
        "executed_notebook_sha256": sha256(executed),
        "stdout_log": str(stdout_path),
        "stdout_sha256": sha256(stdout_path),
        "stderr_log": str(stderr_path),
        "stderr_sha256": sha256(stderr_path),
        "inline_images": inline_images,
        "captured_fit_results": captured_fit_results,
        "error": error,
    }


def run(arguments: argparse.Namespace) -> int:
    source_root = arguments.source_root.resolve()
    output_root = arguments.output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"Refusing to reuse output directory: {output_root}")
    worktree = output_root / "worktree"
    base_revision = arguments.base_revision or git(source_root, "rev-parse", "HEAD")
    patch_path = output_root / "source.diff.patch"
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(source_patch(source_root, base_revision), encoding="utf-8")
    shutil.copytree(
        source_root,
        worktree,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"),
    )
    initial_files = file_map(worktree)
    environment = os.environ.copy()
    home = output_root / "home"
    home.mkdir(parents=True, exist_ok=True)
    environment.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "MPLBACKEND": "module://matplotlib_inline.backend_inline",
        }
    )
    drive, home_path = os.path.splitdrive(str(home))
    environment["HOMEDRIVE"] = drive
    environment["HOMEPATH"] = home_path
    os.environ.update(environment)
    command = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]]
    manifest: dict[str, Any] = {
        "version": 1,
        "label": arguments.label,
        "started_at": now(),
        "source_root": str(source_root),
        "source_remote": git(source_root, "remote", "get-url", "origin"),
        "source_revision": git(source_root, "rev-parse", "HEAD"),
        "source_base_revision": base_revision,
        "source_tree": git(source_root, "rev-parse", "HEAD^{tree}"),
        "source_status": (git(source_root, "status", "--short") or "").splitlines(),
        "source_diff_path": str(patch_path),
        "source_diff_sha256": sha256(patch_path),
        "worktree": str(worktree),
        "initial_file_count": len(initial_files),
        "initial_tree_sha256": tree_sha256(initial_files),
        "environment": environment_metadata(),
        "command": command,
        "working_directory": str(Path.cwd()),
        "notebooks": [],
    }
    (output_root / "command.json").write_text(
        json.dumps({"argv": command, "cwd": str(Path.cwd())}, indent=2), encoding="utf-8"
    )
    failures = 0
    for relative_text in arguments.notebook:
        relative = Path(relative_text)
        source = worktree / relative
        stem = relative.with_suffix("")
        record = execute_notebook(
            source,
            output_root / "executed-notebooks" / relative,
            output_root / "inline-images" / stem,
            output_root / "logs" / stem.with_suffix(".stdout.txt"),
            output_root / "logs" / stem.with_suffix(".stderr.txt"),
            capture_fit_results=arguments.capture_fit_results,
        )
        record["path"] = relative.as_posix()
        manifest["notebooks"].append(record)
        print(f"{arguments.label}: {relative.as_posix()}: {record['status']}", flush=True)
        if record["status"] != "PASSED":
            failures += 1
            break
    final_files = file_map(worktree)
    changed_files = {
        path: metadata
        for path, metadata in final_files.items()
        if path not in initial_files or metadata != initial_files[path]
    }
    generated_records = [
        {"path": str(worktree / relative), "relative_path": relative, **metadata}
        for relative, metadata in sorted(changed_files.items())
    ]
    manifest.update(
        {
            "finished_at": now(),
            "failure_count": failures,
            "exit_code": 1 if failures else 0,
            "status": "PASSED" if failures == 0 else "BLOCKED_REFERENCE"
            if "reference" in arguments.label.lower()
            else "BLOCKED_STAGING",
            "final_file_count": len(final_files),
            "final_tree_sha256": tree_sha256(final_files),
            "generated_or_modified_files": generated_records,
            "file_based_plots": [
                record
                for record in generated_records
                if Path(record["relative_path"]).suffix.lower() in FILE_PLOT_SUFFIXES
            ],
            "reloadable_result_files": [
                record
                for record in generated_records
                if Path(record["relative_path"]).suffix.lower() in RESULT_SUFFIXES
                and ("result" in record["relative_path"].lower() or "/guide/" in f"/{record['relative_path']}")
            ],
        }
    )
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--base-revision")
    parser.add_argument("--notebook", action="append", required=True)
    parser.add_argument("--capture-fit-results", action="store_true")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
