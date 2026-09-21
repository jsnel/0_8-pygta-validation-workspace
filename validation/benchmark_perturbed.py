# /// script
# requires-python = ">=3.10"
# dependencies = ["nbformat>=5.10", "nbclient>=0.10"]
# ///

"""Controlled multi-step fit benchmark for staging optimization diagnostics.

Executes a staging example notebook in memory with a perturbation prelude that
redefines the notebook's ``optimize(...)`` call site so that:

1. the initial free parameters are multiplied by a fixed deterministic
   perturbation (default 1.05, i.e. +5%) before the optimizer runs, and
2. the evaluation budget is raised so the fit performs several genuine
   optimization steps instead of converging in one or two evaluations.

This is a diagnostic instrument. It never modifies the production notebooks
and never writes results into the comparison tree. The perturbation must be
identical for every compared run (baseline vs optimized staging) so the
optimization trajectory and therefore the workload stay comparable.

The public ``Scheme.optimize`` call is timed separately from everything else;
the reported number is the optimizer call duration only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient

PRELUDE = r"""
import functools
import json
import time
from pathlib import Path

import numpy as np

_RECORD_PATH = Path(r"__RECORD_PATH__")
_PERTURB = __PERTURB__
_MAX_NFEV = __MAX_NFEV__
_TARGET_INVOCATION = __TARGET_INVOCATION__
_records = []

from glotaran.project.scheme import Scheme
from glotaran.optimization.optimization import Optimization
from glotaran.optimization.objective import OptimizationObjective

_scheme_optimize = Scheme.optimize
_opt_init = Optimization.__init__
_opt_run = Optimization.run
_obj_calculate = OptimizationObjective.calculate
_obj_get_result = OptimizationObjective.get_result

def _accumulate(name, start):
    _records[-1][name] = _records[-1].get(name, 0.0) + (time.perf_counter() - start)

def _timed_opt_init(self, **kwargs):
    start = time.perf_counter()
    _opt_init(self, **kwargs)
    if _records:
        _accumulate("model_resolve_s", start)

def _timed_calculate(self):
    start = time.perf_counter()
    out = _obj_calculate(self)
    if _records:
        _records[-1]["objective_calls"] = _records[-1].get("objective_calls", 0) + 1
        _accumulate("objective_s", start)
    return out

def _timed_get_result(self):
    start = time.perf_counter()
    out = _obj_get_result(self)
    if _records:
        _accumulate("get_result_s", start)
    return out

Optimization.__init__ = _timed_opt_init
OptimizationObjective.calculate = _timed_calculate
OptimizationObjective.get_result = _timed_get_result

_invocation = {"count": 0}

@functools.wraps(_scheme_optimize)
def _timed_scheme_optimize(self, *args, **kwargs):
    _invocation["count"] += 1
    is_target = _invocation["count"] == _TARGET_INVOCATION
    if is_target and _PERTURB is not None and not kwargs.get("dry_run", False):
        parameters = kwargs.get("parameters") or (args[0] if args else None)
        kwargs["maximum_number_function_evaluations"] = _MAX_NFEV
        for parameter in parameters.all():
            if parameter.vary:
                parameter.value = parameter.value * _PERTURB
    _records.append({
        "invocation": _invocation["count"],
        "is_target": is_target,
        "dry_run": kwargs.get("dry_run", False),
        "max_nfev": kwargs.get("maximum_number_function_evaluations"),
        "perturbed": bool(is_target and _PERTURB is not None and not kwargs.get("dry_run", False)),
    })
    start = time.perf_counter()
    result = _scheme_optimize(self, *args, **kwargs)
    _records[-1]["total_s"] = time.perf_counter() - start
    info = getattr(result, "optimization_info", None)
    if info is not None:
        _records[-1]["nfev"] = getattr(info, "number_of_function_evaluations", None)
        _records[-1]["njev"] = getattr(info, "number_of_jacobian_evaluations", None)
        _records[-1]["nfree"] = len(getattr(info, "free_parameter_labels", []) or [])
        _records[-1]["success"] = getattr(info, "success", None)
        _records[-1]["termination"] = getattr(info, "termination_reason", None)
    _RECORD_PATH.write_text(json.dumps(_records, indent=2))
    return result

Scheme.optimize = _timed_scheme_optimize
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--notebook", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--perturb", type=float, default=1.05)
    parser.add_argument("--max-nfev", type=int, default=60)
    parser.add_argument("--target-invocation", type=int, default=1)
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args()

    source = args.notebook.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    environment = os.environ.copy()
    for name in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "NUMBA_NUM_THREADS",
    ):
        environment[name] = str(args.threads)
    environment["MPLBACKEND"] = "Agg"
    home = output / "home"
    home.mkdir(exist_ok=True)
    environment["HOME"] = str(home)
    environment["USERPROFILE"] = str(home)
    drive, path = os.path.splitdrive(str(home))
    environment["HOMEDRIVE"] = drive
    environment["HOMEPATH"] = path

    with source.open(encoding="utf-8") as stream:
        notebook = nbformat.read(stream, as_version=4)
    for cell in notebook.cells:
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None

    prelude = (
        PRELUDE.replace("__RECORD_PATH__", str(output / "perturbed-records.json"))
        .replace("__PERTURB__", repr(args.perturb))
        .replace("__MAX_NFEV__", repr(args.max_nfev))
        .replace("__TARGET_INVOCATION__", repr(args.target_invocation))
    )
    notebook.cells = [nbformat.v4.new_code_cell(source=prelude), *notebook.cells]

    NotebookClient(
        notebook,
        timeout=None,
        kernel_name="python3",
        resources={"metadata": {"path": str(source.parent)}},
        env=environment,
    ).execute()
    print(f"Perturbed records written to {output / 'perturbed-records.json'}")


if __name__ == "__main__":
    main()
