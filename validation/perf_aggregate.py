# /// script
# requires-python = ">=3.10"
# ///

"""Aggregate fit-call durations from benchmark worker run.json files.

Usage: python validation/perf_aggregate.py <raw_root>
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path


def main() -> None:
    raw = Path(sys.argv[1])
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(raw.rglob("run.json"))]
    rows: dict[tuple[str, str], list[tuple[float, object, object, object]]] = {}
    for run in runs:
        if run.get("warmup") or run.get("status") != "passed":
            continue
        for nb in run["notebooks"]:
            for call in nb["fit_calls"]:
                key = (run["branch"], call["fit_id"])
                workload = call.get("workload") or {}
                rows.setdefault(key, []).append(
                    (
                        call["duration_seconds"],
                        workload.get("number_of_function_evaluations"),
                        workload.get("number_of_jacobian_evaluations"),
                        workload.get("number_of_free_parameters"),
                    )
                )
    for key in sorted(rows):
        entries = rows[key]
        vals = [v[0] for v in entries]
        nfev = {v[1] for v in entries}
        njev = {v[2] for v in entries}
        nfp = {v[3] for v in entries}
        print(
            f"{key[0]:8s} {key[1]:28s} n={len(vals)} "
            f"mean={statistics.fmean(vals):.4f} med={statistics.median(vals):.4f} "
            f"std={statistics.stdev(vals):.4f} min={min(vals):.4f} max={max(vals):.4f} "
            f"nfev={sorted(map(str, nfev))} njev={sorted(map(str, njev))} nfree={sorted(map(str, nfp))}"
        )


if __name__ == "__main__":
    main()
