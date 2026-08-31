"""Create machine- and human-readable inventories for external case studies."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import nbformat
import yaml


LEGACY_SECTIONS = (
    "default_megacomplex",
    "dataset_groups",
    "megacomplex",
    "k_matrix",
    "initial_concentration",
    "irf",
    "dataset",
    "weights",
    "clp_constraints",
    "clp_relations",
    "clp_area_penalties",
)
PATH_PATTERN = re.compile(
    r"['\"]([^'\"]+\.(?:ascii|csv|ipynb|nc|png|svg|pdf|ya?ml))['\"]",
    re.IGNORECASE,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(path: Path, *arguments: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *arguments],
        check=check,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def git_lines(path: Path, *arguments: str) -> list[str]:
    output = git(path, *arguments)
    return output.splitlines() if output else []


def notebook_inventory(path: Path, relative: str) -> dict[str, Any]:
    notebook = nbformat.read(path, as_version=4)
    code = "\n".join(cell.source for cell in notebook.cells if cell.cell_type == "code")
    referenced_paths = sorted(set(PATH_PATTERN.findall(code)))
    return {
        "path": relative,
        "sha256": sha256(path),
        "kernel": notebook.metadata.get("kernelspec", {}).get("name"),
        "cell_count": len(notebook.cells),
        "code_cell_count": sum(cell.cell_type == "code" for cell in notebook.cells),
        "existing_output_count": sum(
            len(cell.get("outputs", [])) for cell in notebook.cells if cell.cell_type == "code"
        ),
        "fit_call_count": len(re.findall(r"(?<![\w.])optimize\s*\(", code))
        + len(re.findall(r"\.optimize\s*\(", code)),
        "scheme_constructor_count": len(re.findall(r"\bScheme\s*\(", code)),
        "load_scheme_count": len(re.findall(r"\bload_scheme\s*\(", code)),
        "dry_run_count": len(re.findall(r"dry_run\s*=\s*True", code)),
        "random_seed_mentions": sorted(
            set(re.findall(r"[^\n]*(?:random_seed|random\.seed|np\.random\.seed)[^\n]*", code))
        ),
        "referenced_paths": referenced_paths,
        "expected_written_paths": sorted(
            path for path in referenced_paths if path.startswith(("results/", "guide/"))
        ),
    }


def model_inventory(path: Path, relative: str) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        return {"path": relative, "sha256": sha256(path), "parse_error": repr(error)}
    if not isinstance(document, dict):
        return {
            "path": relative,
            "sha256": sha256(path),
            "top_level_type": type(document).__name__,
        }
    datasets = document.get("dataset") or {}
    groups = document.get("dataset_groups") or {}
    megacomplexes = document.get("megacomplex") or {}
    default_type = document.get("default_megacomplex")
    types = sorted(
        {
            str(item.get("type", default_type))
            for item in megacomplexes.values()
            if isinstance(item, dict) and item.get("type", default_type) is not None
        }
    )
    dataset_details = {}
    for label, item in datasets.items() if isinstance(datasets, dict) else ():
        if isinstance(item, dict):
            dataset_details[str(label)] = {
                key: item.get(key)
                for key in (
                    "megacomplex",
                    "global_megacomplex",
                    "megacomplex_scale",
                    "global_megacomplex_scale",
                    "initial_concentration",
                    "irf",
                    "scale",
                )
                if key in item
            }
    return {
        "path": relative,
        "sha256": sha256(path),
        "top_level_keys": list(document),
        "legacy_sections": [key for key in LEGACY_SECTIONS if key in document],
        "dataset_groups": list(groups) if isinstance(groups, dict) else [],
        "datasets": dataset_details,
        "megacomplex_types": types,
        "megacomplex_count": len(megacomplexes) if isinstance(megacomplexes, dict) else None,
        "k_matrix_count": len(document.get("k_matrix") or {}),
        "irf_count": len(document.get("irf") or {}),
        "initial_concentration_count": len(document.get("initial_concentration") or {}),
        "clp_constraint_count": len(document.get("clp_constraints") or []),
        "clp_relation_count": len(document.get("clp_relations") or []),
        "clp_area_penalty_count": len(document.get("clp_area_penalties") or []),
        "weight_count": len(document.get("weights") or []),
    }


def repository_inventory(workspace: Path, specification: dict[str, Any]) -> dict[str, Any]:
    slug = specification["slug"]
    reference = workspace / "temp" / "case-studies" / slug / "reference"
    staging = workspace / "temp" / "case-studies" / slug / "staging"
    source_commit = git(reference, "rev-parse", "HEAD")
    staging_revision = git(staging, "rev-parse", "HEAD")
    staging_base = (
        git(staging, "merge-base", source_commit, staging_revision, check=False)
        or staging_revision
    )
    reference_tree = git(reference, "rev-parse", "HEAD^{tree}")
    staging_base_tree = git(staging, "rev-parse", f"{staging_base}^{{tree}}")
    tracked = git_lines(reference, "ls-files")
    files = []
    for relative in tracked:
        path = reference / relative
        if path.is_file():
            files.append(
                {
                    "path": relative,
                    "size": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    extension_counts = Counter(Path(item["path"]).suffix.lower() or "[none]" for item in files)
    selected = list(specification["notebooks"])
    notebooks = [notebook_inventory(reference / relative, relative) for relative in selected]
    model_paths = [
        relative
        for relative in tracked
        if "/models/" in f"/{relative}" and Path(relative).suffix.lower() in {".yml", ".yaml"}
    ]
    dependencies = {}
    for name in ("requirements.txt", "environment.yml", "pyproject.toml", "tox.ini"):
        path = reference / name
        if path.is_file():
            dependencies[name] = {
                "sha256": sha256(path),
                "content": path.read_text(encoding="utf-8"),
            }
    return {
        "slug": slug,
        "url": specification["url"],
        "selection_rationale": specification["rationale"],
        "reference_path": str(reference.resolve()),
        "staging_path": str(staging.resolve()),
        "default_branch": git(reference, "branch", "--show-current"),
        "source_commit": source_commit,
        "reference_tree": reference_tree,
        "staging_base_commit": staging_base,
        "staging_base_tree": staging_base_tree,
        "staging_revision": staging_revision,
        "staging_tree": git(staging, "rev-parse", "HEAD^{tree}"),
        "matching_initial_trees": reference_tree == staging_base_tree,
        "reference_status": git_lines(reference, "status", "--short"),
        "staging_status": git_lines(staging, "status", "--short"),
        "submodules": git_lines(reference, "submodule", "status", "--recursive"),
        "lfs_files": git_lines(reference, "lfs", "ls-files", "--all"),
        "tracked_file_count": len(files),
        "tracked_tree_sha256": tree_digest(files),
        "extension_counts": dict(sorted(extension_counts.items())),
        "files": files,
        "dependencies": dependencies,
        "notebooks": notebooks,
        "models": [model_inventory(reference / relative, relative) for relative in model_paths],
    }


def tree_digest(files: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for item in files:
        digest.update(item["path"].encode())
        digest.update(b"\0")
        digest.update(item["sha256"].encode())
        digest.update(b"\0")
    return digest.hexdigest()


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# External case-study inventory",
        "",
        f"Configuration: `{report['configuration']}`",
        "",
    ]
    for repository in report["repositories"]:
        lines.extend(
            [
                f"## {repository['slug']}",
                "",
                f"- URL: {repository['url']}",
                f"- Source commit: `{repository['source_commit']}`",
                f"- Matching initial trees: `{repository['matching_initial_trees']}`",
                f"- Tracked files: {repository['tracked_file_count']}",
                f"- Submodules: {len(repository['submodules'])}; Git LFS files: {len(repository['lfs_files'])}",
                f"- Selection: {repository['selection_rationale']}",
                "",
                "| Notebook | Fits | Scheme constructors | Existing outputs |",
                "|---|---:|---:|---:|",
            ]
        )
        for notebook in repository["notebooks"]:
            lines.append(
                f"| {notebook['path']} | {notebook['fit_call_count']} | "
                f"{notebook['scheme_constructor_count']} | {notebook['existing_output_count']} |"
            )
        lines.extend(
            [
                "",
                f"Model files inventoried: {len(repository['models'])}.",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--slug")
    arguments = parser.parse_args()
    config = yaml.safe_load(arguments.config.read_text(encoding="utf-8"))
    specifications = [
        item
        for item in config["repositories"]
        if arguments.slug is None or item["slug"] == arguments.slug
    ]
    if not specifications:
        parser.error(f"Unknown case-study slug: {arguments.slug}")
    report = {
        "version": 1,
        "configuration": str(arguments.config.resolve()),
        "repositories": [
            repository_inventory(arguments.workspace.resolve(), item)
            for item in specifications
        ],
    }
    arguments.output_root.mkdir(parents=True, exist_ok=True)
    (arguments.output_root / "inventory.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (arguments.output_root / "inventory.md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
