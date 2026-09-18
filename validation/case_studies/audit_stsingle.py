"""Audit persisted ST decompositions without changing comparison acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr
import yaml

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compatibility.metrics import compare_arrays  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _data_array(path: Path, preferred: str | None = None) -> xr.DataArray:
    dataset = xr.load_dataset(path)
    if preferred and preferred in dataset:
        return dataset[preferred]
    if len(dataset.data_vars) != 1 and preferred is None:
        raise ValueError(f"Ambiguous data variables in {path}: {list(dataset.data_vars)}")
    return dataset[preferred] if preferred else next(iter(dataset.data_vars.values()))


def reconstruct_fit(matrix: xr.DataArray, clp: xr.DataArray, global_matrix: xr.DataArray) -> xr.DataArray:
    """Reconstruct ``time,spectral`` using named CLP dimensions."""
    global_clp = xr.dot(global_matrix, clp, dim="global_clp_label")
    return xr.dot(global_clp, matrix, dim="clp_label").transpose("time", "spectral")


def residual_reorder_proof(
    residual: xr.DataArray, data: xr.DataArray, fitted_data: xr.DataArray
) -> dict[str, Any]:
    """Undo the v0.7 flat-vector reshape and test against the independent fit."""
    reordered = xr.DataArray(
        residual.transpose("spectral", "time").values.reshape(
            data.sizes["time"], data.sizes["spectral"]
        ),
        dims=("time", "spectral"),
        coords={"time": data.time, "spectral": data.spectral},
    )
    from_data = data - fitted_data
    return compare_arrays(reordered, from_data, rtol=1e-10, atol=1e-8)


def _result_file(root: Path) -> Path:
    for name in ("result.yml", "result.yaml"):
        path = root / name
        if path.is_file():
            return path
    raise FileNotFoundError(f"No result.yml/result.yaml in {root}")


def _reference_files(root: Path, document: dict[str, Any], label: str) -> dict[str, Path]:
    entry = (document.get("data") or {}).get(label, f"{label}.nc")
    path = root / entry
    if not path.is_file():
        path = root / f"{label}.nc"
    return {"result": _result_file(root), "data": path}


def _staging_files(root: Path, document: dict[str, Any], label: str) -> dict[str, Path]:
    entry = (document.get("optimization_results") or {}).get(label) or {}
    dataset_root = root / "optimization_results" / label
    files = {"result": _result_file(root)}
    for key, name in (("input", "input_data"), ("fitted", "fitted_data")):
        relative = entry.get(name)
        if relative:
            files[key] = dataset_root / relative
    return files


def audit(reference: Path, staging: Path) -> dict[str, Any]:
    reference_doc = yaml.safe_load(_result_file(reference).read_text(encoding="utf-8")) or {}
    staging_doc = yaml.safe_load(_result_file(staging).read_text(encoding="utf-8")) or {}
    ref_labels = set((reference_doc.get("data") or {}))
    stage_labels = set((staging_doc.get("optimization_results") or {}))
    records: dict[str, Any] = {}
    hashes: dict[str, str] = {}
    for label in sorted(ref_labels | stage_labels):
        record: dict[str, Any] = {}
        if label not in ref_labels or label not in stage_labels:
            record["status"] = "MISSING_ARTIFACT"
            records[label] = record
            continue
        ref_files = _reference_files(reference, reference_doc, label)
        stage_files = _staging_files(staging, staging_doc, label)
        for path in (*ref_files.values(), *stage_files.values()):
            if path.is_file():
                hashes[str(path)] = _sha256(path)
        ref_raw = _data_array(ref_files["data"], "data")
        stage_input = _data_array(stage_files["input"], "data")
        stage_fit = _data_array(stage_files["fitted"])
        ref_nc = xr.load_dataset(ref_files["data"])
        reconstructed = reconstruct_fit(ref_nc["matrix"], ref_nc["clp"], ref_nc["global_matrix"])
        record["raw_ref_to_stage"] = {
            "fitted_data": compare_arrays(ref_nc["fitted_data"], stage_fit, rtol=1e-5, atol=1e-8),
            "input_exact": compare_arrays(ref_raw, stage_input, rtol=0.0, atol=0.0),
        }
        record["ref_stored_to_own_reconstructed"] = compare_arrays(
            ref_nc["fitted_data"], reconstructed, rtol=1e-5, atol=1e-8
        )
        record["ref_reconstructed_to_stage_native"] = compare_arrays(
            reconstructed, stage_fit, rtol=1e-5, atol=1e-8
        )
        record["ref_residual_reorder_proof"] = residual_reorder_proof(
            ref_nc["residual"], ref_nc["data"], reconstructed
        )
        records[label] = record
    return {
        "version": 1,
        "diagnostic_only": True,
        "acceptance_status": "REVIEW_REQUIRED",
        "reference": str(reference),
        "staging": str(staging),
        "datasets": records,
        "source_file_sha256": hashes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.reference.resolve(), args.staging.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "datasets": len(report["datasets"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
