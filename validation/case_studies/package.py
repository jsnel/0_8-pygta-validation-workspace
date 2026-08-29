"""Assemble and verify visual-review manifests for one final case-study run."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import nbformat
import yaml


VALIDATION_PATTERN = re.compile(
    r"MIGRATION_VALIDATION scheme=(?P<scheme>\S+) (?P<checks>.+)$", re.MULTILINE
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git(path: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", "-C", str(path), *arguments], text=True).strip()


def artifact(path: str | Path, kind: str) -> dict[str, Any]:
    path = Path(path).resolve()
    return {"kind": kind, "path": str(path), "size": path.stat().st_size, "sha256": sha256(path)}


def artifacts_for_run(manifest: dict[str, Any], manifest_path: Path, side: str) -> list[dict[str, Any]]:
    result = [artifact(manifest_path, f"{side}_run_manifest")]
    result.append(artifact(manifest_path.parent / "command.json", f"{side}_command"))
    result.append(artifact(manifest["source_diff_path"], f"{side}_source_patch"))
    for notebook in manifest["notebooks"]:
        result.extend(
            [
                artifact(notebook["executed_notebook"], f"{side}_executed_notebook"),
                artifact(notebook["stdout_log"], f"{side}_stdout"),
                artifact(notebook["stderr_log"], f"{side}_stderr"),
            ]
        )
        result.extend(artifact(image["path"], f"{side}_inline_image") for image in notebook["inline_images"])
    result.extend(artifact(item["path"], f"{side}_file_plot") for item in manifest["file_based_plots"])
    result.extend(artifact(item["path"], f"{side}_result") for item in manifest["reloadable_result_files"])
    unique = {item["path"]: item for item in result}
    return list(unique.values())


def validation_evidence(staging_manifest: dict[str, Any], schema_report: dict[str, Any]) -> dict[str, Any]:
    messages = []
    for notebook in staging_manifest["notebooks"]:
        text = Path(notebook["stdout_log"]).read_text(encoding="utf-8")
        messages.extend(match.groupdict() for match in VALIDATION_PATTERN.finditer(text))
    dry = [item for item in messages if "load=PASS" in item["checks"] and "dry_run=PASS" in item["checks"]]
    real = [item for item in messages if "real_fit=PASS" in item["checks"]]
    return {
        "schema_report_scheme_count": schema_report["scheme_count"],
        "parameter_aware_schema_pass_count": sum(
            item["parameter_aware_schema"] == "PASS" for item in schema_report["schemes"]
        ),
        "parameter_aware_schema_not_practical_count": sum(
            item["parameter_aware_schema"] == "NOT_PRACTICAL" for item in schema_report["schemes"]
        ),
        "strict_load_all_passed": schema_report["all_passed"],
        "load_and_dry_run_pass_count": len(dry),
        "real_fit_pass_count": len(real),
        "messages": messages,
    }


def environment_record(
    manifest: dict[str, Any], source_checkout: Path, distribution_snapshot: Path
) -> dict[str, Any]:
    environment = manifest["environment"]
    snapshot = load(distribution_snapshot)
    checkout_candidates = [source_checkout / "uv.lock", source_checkout / "pyproject.toml"]
    lockfiles = [artifact(path, "environment_lock") for path in checkout_candidates if path.is_file()]
    return {
        **environment,
        "metadata_sha256": json_hash(environment),
        "pyglotaran_revision": git(source_checkout / "pyglotaran", "rev-parse", "HEAD"),
        "orchestration_revision": git(source_checkout, "rev-parse", "HEAD"),
        "examples_revision": git(source_checkout / "pyglotaran-examples", "rev-parse", "HEAD"),
        "extras_revision": git(source_checkout / "pyglotaran-extras", "rev-parse", "HEAD"),
        "lockfiles": lockfiles,
        "installed_distributions": {
            "path": str(distribution_snapshot.resolve()),
            "sha256": sha256(distribution_snapshot),
            "count": snapshot["distribution_count"],
            "distributions_sha256": snapshot["distributions_sha256"],
        },
    }


def markdown(repository: dict[str, Any]) -> str:
    counts = repository["artifact_counts"]
    lines = [
        f"# Visual-review manifest: {repository['slug']}",
        "",
        f"Status: **{repository['status']}**",
        "",
        "Automated evidence only. No subjective visual review, scientific parity decision, or root-cause classification has been performed.",
        "",
        f"- Source base: `{repository['source_revision']}`",
        f"- Staging commit: `{repository['staging_revision']}` on `{repository['staging_branch']}`",
        f"- Reference/staging notebooks: {counts['reference_notebooks']}/{counts['staging_notebooks']}",
        f"- Inline images: {counts['reference_inline_images']}/{counts['staging_inline_images']}",
        f"- File plots: {counts['reference_file_plots']}/{counts['staging_file_plots']}",
        f"- Reloadable result artifacts: {counts['reference_results']}/{counts['staging_results']}",
        f"- Provisional comparison: **{repository['comparison']['provisional_status']}**",
        "",
        "## Review-required automated observations",
        "",
    ]
    if repository["known_mismatches"]:
        for item in repository["known_mismatches"]:
            lines.append(
                f"- `{item['result']}`: {item['status']}; worst fitted-data normalized RMS "
                f"{item['worst_fitted_data_normalized_rms']}."
            )
    else:
        lines.append("- None reported by the automated comparator.")
    lines.extend(
        [
            "",
            f"Comparison report: `{repository['comparison']['json']}`",
            f"Schema/load report: `{repository['migration_validation']['schema_report']}`",
            "",
        ]
    )
    return "\n".join(lines)


def build(args: argparse.Namespace) -> dict[str, Any]:
    workspace = args.workspace.resolve()
    run_root = (workspace / "validation" / "runs" / "case-studies" / args.timestamp).resolve()
    comparison_root = (
        workspace / "validation" / "comparisons" / "case-studies" / args.timestamp
    ).resolve()
    config = yaml.safe_load((workspace / "validation/case_studies/cases.yml").read_text(encoding="utf-8"))
    inventory = load(run_root / "inventory.json")
    inventory_by_slug = {item["slug"]: item for item in inventory["repositories"]}
    tests = load(args.test_record.resolve()) if args.test_record else {}
    validation_side_changed_files = subprocess.run(
        [
            "git",
            "status",
            "--short",
            "--",
            ".gitignore",
            "validation/case_studies",
            "validation/tests/test_case_studies.py",
            "validation/logs/validation-log.md",
            "changelog.md",
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()
    repositories = []
    reference_distribution_snapshot = run_root / "environments/reference.json"
    staging_distribution_snapshot = run_root / "environments/staging.json"
    all_artifacts = [
        artifact(workspace / "validation/case_studies/cases.yml", "case_study_contract"),
        artifact(workspace / "validation/logs/validation-log.md", "validation_log"),
        artifact(workspace / "changelog.md", "validation_changelog"),
        artifact(run_root / "inventory.json", "inventory"),
        artifact(run_root / "inventory.md", "inventory"),
        artifact(run_root / "migration-log.json", "migration_log"),
        artifact(run_root / "migration-log.md", "migration_log"),
        artifact(reference_distribution_snapshot, "installed_distributions"),
        artifact(staging_distribution_snapshot, "installed_distributions"),
    ]
    reference_package = workspace / "temp/pyglotaran-main-dev"
    staging_package = workspace / "temp/pyglotaran-staging-dev"
    for specification in config["repositories"]:
        slug = specification["slug"]
        repository_root = run_root / slug
        reference_manifest_path = repository_root / "reference/manifest.json"
        staging_manifest_path = repository_root / "staging/manifest.json"
        reference_manifest = load(reference_manifest_path)
        staging_manifest = load(staging_manifest_path)
        comparison_json = comparison_root / slug / "comparison.json"
        comparison_md = comparison_json.with_suffix(".md")
        schema_json = comparison_root / slug / "schema-validation.json"
        schema_md = schema_json.with_suffix(".md")
        comparison = load(comparison_json)
        schema = load(schema_json)
        artifacts = artifacts_for_run(reference_manifest, reference_manifest_path, "reference")
        artifacts.extend(artifacts_for_run(staging_manifest, staging_manifest_path, "staging"))
        artifacts.extend(
            [
                artifact(run_root / "inventory.json", "inventory"),
                artifact(run_root / "inventory.md", "inventory"),
                artifact(run_root / "migration-log.json", "migration_log"),
                artifact(run_root / "migration-log.md", "migration_log"),
                artifact(reference_distribution_snapshot, "installed_distributions"),
                artifact(staging_distribution_snapshot, "installed_distributions"),
                artifact(comparison_json, "comparison"),
                artifact(comparison_md, "comparison"),
                artifact(schema_json, "schema_validation"),
                artifact(schema_md, "schema_validation"),
            ]
        )
        artifacts.extend(artifact(item["schema"], "parameter_aware_schema") for item in schema["schemes"])
        if args.test_record:
            artifacts.append(artifact(args.test_record.resolve(), "test_record"))
            artifacts.extend(artifact(path, "test_artifact") for path in tests.get("artifacts", []))
        artifacts = list({item["path"]: item for item in artifacts}.values())
        all_artifacts.extend(artifacts)
        validation = validation_evidence(staging_manifest, schema)
        validation["expected_fit_invocations"] = sum(
            notebook["fit_call_count"] for notebook in inventory_by_slug[slug]["notebooks"]
        )
        validation["schema_report"] = str(schema_json.resolve())
        missing = comparison["summary"]["status_counts"]["MISSING_ARTIFACT"]
        reference_inline_images = sum(
            len(item["inline_images"]) for item in reference_manifest["notebooks"]
        )
        staging_inline_images = sum(
            len(item["inline_images"]) for item in staging_manifest["notebooks"]
        )
        status = (
            "READY_FOR_VISUAL_REVIEW"
            if reference_manifest["status"] == "PASSED"
            and staging_manifest["status"] == "PASSED"
            and schema["all_passed"]
            and missing == 0
            and validation["load_and_dry_run_pass_count"]
            == validation["expected_fit_invocations"]
            and validation["real_fit_pass_count"] == validation["expected_fit_invocations"]
            and reference_inline_images > 0
            and staging_inline_images > 0
            and all(item["inline_images"] for item in reference_manifest["notebooks"])
            and all(item["inline_images"] for item in staging_manifest["notebooks"])
            else "BLOCKED_STAGING"
        )
        mismatches = []
        for result in comparison["results"]:
            if result["status"] == "PASS":
                continue
            values = [
                dataset.get("variables", {}).get("fitted_data", {}).get("normalized_rms")
                for dataset in result.get("datasets", [])
            ]
            mismatches.append(
                {
                    "result": result["result"],
                    "status": result["status"],
                    "reason": result.get("reason"),
                    "worst_fitted_data_normalized_rms": max(
                        (value for value in values if value is not None), default=None
                    ),
                }
            )
        reference_source = Path(reference_manifest["source_root"])
        staging_source = Path(staging_manifest["source_root"])
        record = {
            "slug": slug,
            "url": specification["url"],
            "status": status,
            "source_revision": reference_manifest["source_revision"],
            "source_tree": reference_manifest["source_tree"],
            "submodules": inventory_by_slug[slug]["submodules"],
            "git_lfs_files": inventory_by_slug[slug]["lfs_files"],
            "matching_initial_trees": inventory_by_slug[slug]["matching_initial_trees"],
            "staging_base_revision": staging_manifest["source_base_revision"],
            "staging_revision": staging_manifest["source_revision"],
            "staging_branch": git(staging_source, "branch", "--show-current"),
            "staging_diff": {
                "path": staging_manifest["source_diff_path"],
                "sha256": staging_manifest["source_diff_sha256"],
            },
            "checkout_status": {
                "reference": reference_manifest["source_status"],
                "staging": staging_manifest["source_status"],
            },
            "environments": {
                "reference": environment_record(
                    reference_manifest, reference_package, reference_distribution_snapshot
                ),
                "staging": environment_record(
                    staging_manifest, staging_package, staging_distribution_snapshot
                ),
            },
            "selection_rationale": specification["rationale"],
            "selected_entry_points": specification["notebooks"],
            "inventory": str((run_root / "inventory.json").resolve()),
            "migration_log": str((run_root / "migration-log.json").resolve()),
            "changed_source_files": git(
                staging_source,
                "diff",
                "--name-status",
                f"{staging_manifest['source_base_revision']}..HEAD",
            ).splitlines(),
            "validation_side_changed_files": validation_side_changed_files,
            "tests": tests,
            "commands": {
                "reference_runner": reference_manifest["command"],
                "staging_runner": staging_manifest["command"],
                "comparison": [
                    str((workspace / "validation/case_studies/compare.py").resolve()),
                    "--reference",
                    str((repository_root / "reference/worktree").resolve()),
                    "--staging",
                    str((repository_root / "staging/worktree").resolve()),
                    "--slug",
                    slug,
                    "--output",
                    str(comparison_json.resolve()),
                ],
                "schema_validation": [
                    str((workspace / "validation/case_studies/validate_schemas.py").resolve()),
                    "--root",
                    str(staging_source.resolve()),
                    "--slug",
                    slug,
                    "--output",
                    str(schema_json.resolve()),
                ],
            },
            "reference_run": str(reference_manifest_path.resolve()),
            "staging_run": str(staging_manifest_path.resolve()),
            "runner_exit_codes": {
                "reference": reference_manifest.get(
                    "exit_code", 1 if reference_manifest["failure_count"] else 0
                ),
                "staging": staging_manifest.get(
                    "exit_code", 1 if staging_manifest["failure_count"] else 0
                ),
            },
            "migration_validation": validation,
            "comparison": {
                "json": str(comparison_json.resolve()),
                "markdown": str(comparison_md.resolve()),
                "provisional_status": comparison["summary"]["provisional_status"],
                "status_counts": comparison["summary"]["status_counts"],
            },
            "known_mismatches": mismatches,
            "missing_artifacts": missing,
            "blockers": [],
            "artifact_counts": {
                "reference_notebooks": len(reference_manifest["notebooks"]),
                "staging_notebooks": len(staging_manifest["notebooks"]),
                "reference_inline_images": reference_inline_images,
                "staging_inline_images": staging_inline_images,
                "reference_file_plots": len(reference_manifest["file_based_plots"]),
                "staging_file_plots": len(staging_manifest["file_based_plots"]),
                "reference_results": len(reference_manifest["reloadable_result_files"]),
                "staging_results": len(staging_manifest["reloadable_result_files"]),
            },
            "artifacts": artifacts,
        }
        per_repository_json = repository_root / "visual-review-manifest.json"
        per_repository_md = repository_root / "visual-review-manifest.md"
        per_repository_json.write_text(json.dumps(record, indent=2), encoding="utf-8")
        per_repository_md.write_text(markdown(record), encoding="utf-8")
        all_artifacts.extend(
            [artifact(per_repository_json, "repository_manifest"), artifact(per_repository_md, "repository_manifest")]
        )
        repositories.append(record)
    root_status = (
        "READY_FOR_VISUAL_REVIEW"
        if all(item["status"] == "READY_FOR_VISUAL_REVIEW" for item in repositories)
        else "BLOCKED"
    )
    if args.test_record:
        all_artifacts.append(artifact(args.test_record.resolve(), "test_record"))
        all_artifacts.extend(artifact(path, "test_artifact") for path in tests.get("artifacts", []))
    return {
        "version": 1,
        "timestamp": args.timestamp,
        "status": root_status,
        "repositories": repositories,
        "validation_side_changed_files": validation_side_changed_files,
        "tests": tests,
        "orchestration_notes": [],
        "classification_notice": "Stops before subjective visual review, scientific parity, final difference classification, or root-cause classification.",
        "artifacts": list({item["path"]: item for item in all_artifacts}.values()),
    }


def top_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# External case-study visual-review handoff",
        "",
        f"Timestamp: `{report['timestamp']}`",
        f"Overall status: **{report['status']}**",
        "",
        report["classification_notice"],
        "",
        "| Repository | Status | Provisional comparison | Notebooks (reference/staging) |",
        "|---|---|---|---:|",
    ]
    for item in report["repositories"]:
        counts = item["artifact_counts"]
        lines.append(
            f"| {item['slug']} | **{item['status']}** | {item['comparison']['provisional_status']} | "
            f"{counts['reference_notebooks']}/{counts['staging_notebooks']} |"
        )
    lines.append("")
    return "\n".join(lines)


def verify(manifest_path: Path) -> dict[str, Any]:
    report = load(manifest_path)
    errors = []
    checked = 0
    for item in report["artifacts"]:
        path = Path(item["path"])
        if not path.is_file():
            errors.append(f"missing:{path}")
            continue
        checked += 1
        if sha256(path) != item["sha256"]:
            errors.append(f"hash:{path}")
        if item["kind"].endswith("executed_notebook"):
            try:
                nbformat.read(path, as_version=4)
            except Exception as error:  # noqa: BLE001 - verifier reports exact unreadable artifact
                errors.append(f"notebook:{path}:{error!r}")
    return {"status": "PASS" if not errors else "FAIL", "checked_artifacts": checked, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--timestamp", required=True)
    parser.add_argument("--test-record", type=Path)
    args = parser.parse_args()
    run_root = args.workspace.resolve() / "validation/runs/case-studies" / args.timestamp
    report = build(args)
    json_path = run_root / "visual-review-manifest.json"
    md_path = run_root / "visual-review-manifest.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(top_markdown(report), encoding="utf-8")
    verification = verify(json_path)
    verification_path = run_root / "verification.json"
    verification_path.write_text(json.dumps(verification, indent=2), encoding="utf-8")
    print(top_markdown(report))
    print(json.dumps(verification, indent=2))
    return 0 if report["status"] == "READY_FOR_VISUAL_REVIEW" and verification["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
