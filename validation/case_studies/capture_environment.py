"""Capture a pip-independent installed-distribution snapshot for evidence packages."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from datetime import datetime
from datetime import timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    distributions = sorted(
        (
            {
                "name": distribution.metadata.get("Name", ""),
                "version": distribution.version,
            }
            for distribution in importlib.metadata.distributions()
        ),
        key=lambda item: (item["name"].lower(), item["version"]),
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
    distribution_json = json.dumps(distributions, sort_keys=True).encode()
    report = {
        "version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "thread_and_plot_environment": relevant_environment,
        "distribution_count": len(distributions),
        "distributions_sha256": hashlib.sha256(distribution_json).hexdigest(),
        "distributions": distributions,
        "command": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        "working_directory": str(Path.cwd()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Captured {len(distributions)} distributions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
