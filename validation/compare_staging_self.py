# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pandas", "xarray", "pyyaml"]
# ///

"""Compare two staging v0.8 result trees (e.g. baseline vs optimized staging).

Both trees are loaded through the same v0.8 compatibility loader and compared
with the same semantic-array metrics used by the cross-version comparison, so
the acceptance gates are the scenario tolerances. Use this to confirm that an
optimization preserves the baseline staging outcomes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compare_results import load_manifest  # noqa: E402
from compatibility.load_v08 import load_v08_result  # noqa: E402
from compatibility.metrics import compare_arrays  # noqa: E402

DEFAULT_RTOL = 1e-5
DEFAULT_ATOL = 1e-8


def _scenario_tolerances(manifest: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for scenario in manifest.get("scenarios", []):
        out[scenario["id"]] = scenario
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--optimized-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    scenarios = _scenario_tolerances(manifest)

    baseline_root = args.baseline_root.resolve()
    optimized_root = args.optimized_root.resolve()

    baseline_leaves = {p.parent.relative_to(baseline_root).as_posix(): p.parent for p in baseline_root.rglob("result.yml")}
    optimized_leaves = {p.parent.relative_to(optimized_root).as_posix(): p.parent for p in optimized_root.rglob("result.yml")}

    report: dict = {"baseline_root": str(baseline_root), "optimized_root": str(optimized_root), "scenarios": []}
    worst_status_rank = 0
    status_rank = {"pass": 0, "different": 1, "missing": 2, "structural_mismatch": 3}

    for leaf in sorted(set(baseline_leaves) | set(optimized_leaves)):
        entry: dict = {"scenario": leaf, "variables": {}, "status": "pass"}
        if leaf not in baseline_leaves:
            entry["status"] = "missing"
            entry["note"] = "missing in baseline"
        elif leaf not in optimized_leaves:
            entry["status"] = "missing"
            entry["note"] = "missing in optimized"
        else:
            base = load_v08_result(baseline_leaves[leaf])
            opt = load_v08_result(optimized_leaves[leaf])
            scenario_cfg = scenarios.get(leaf, {})
            rtol = scenario_cfg.get("rtol", DEFAULT_RTOL)
            atol = scenario_cfg.get("atol", DEFAULT_ATOL)
            base_datasets = getattr(base, "datasets", {})
            opt_datasets = getattr(opt, "datasets", {})
            for dlabel in sorted(set(base_datasets) | set(opt_datasets)):
                bd = base_datasets.get(dlabel)
                od = opt_datasets.get(dlabel)
                if bd is None or od is None:
                    entry["variables"][dlabel] = {"status": "missing"}
                    entry["status"] = "missing"
                    continue
                for var in sorted(set(bd.variables) | set(od.variables)):
                    bv = bd.variables.get(var)
                    ov = od.variables.get(var)
                    if bv is None or ov is None:
                        entry["variables"][f"{dlabel}/{var}"] = {"status": "missing"}
                        continue
                    metric = compare_arrays(bv, ov, rtol=rtol, atol=atol)
                    key = f"{dlabel}/{var}"
                    entry["variables"][key] = metric
                    if status_rank.get(metric["status"], 3) > status_rank[entry["status"]]:
                        entry["status"] = metric["status"]
            # parameters
            base_params = getattr(base, "parameters", None)
            opt_params = getattr(opt, "parameters", None)
            if base_params is not None and opt_params is not None:
                bs = base_params.set_index("label")["value"]
                os_ = opt_params.set_index("label")["value"]
                shared = bs.index.intersection(os_.index)
                bvv = bs.loc[shared].to_numpy(dtype=float)
                ovv = os_.loc[shared].to_numpy(dtype=float)
                ok = np.allclose(bvv, ovv, rtol=rtol, atol=atol, equal_nan=True)
                entry["parameters"] = {
                    "status": "pass" if ok else "different",
                    "shared": len(shared),
                    "max_rel": float(np.max(np.abs(bvv - ovv) / np.maximum(np.abs(bvv), np.finfo(float).eps))) if len(shared) else None,
                }
                if not ok:
                    entry["status"] = "different"
        report["scenarios"].append(entry)
        worst_status_rank = max(worst_status_rank, status_rank.get(entry["status"], 3))

    report["summary"] = {
        "total": len(report["scenarios"]),
        "pass": sum(1 for s in report["scenarios"] if s["status"] == "pass"),
        "different": sum(1 for s in report["scenarios"] if s["status"] == "different"),
        "missing": sum(1 for s in report["scenarios"] if s["status"] == "missing"),
        "structural_mismatch": sum(1 for s in report["scenarios"] if s["status"] == "structural_mismatch"),
        "acceptable": worst_status_rank == 0,
    }

    text = json.dumps(report, indent=2, default=float)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    for s in report["scenarios"]:
        if s["status"] != "pass":
            print(f"  {s['status'].upper()}: {s['scenario']}")
    return 0 if report["summary"]["acceptable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
