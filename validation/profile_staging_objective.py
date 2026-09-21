# /// script
# requires-python = ">=3.10"
# dependencies = ["nbformat>=5.10", "nbclient>=0.10"]
# ///

"""Phase-capture profiling of a staging example notebook's optimize call.

Inserts a prelude that wraps ``Scheme.optimize`` to time, per invocation:
total call, model resolution (``Optimization.__init__``), objective calls
(matrix calculation / reduction / estimation, SVD in result construction),
result construction, and peak RSS delta.

Diagnostic only: writes a JSON summary; the notebook's saved results are
written into a temporary output directory, not the workspace.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from copy import deepcopy
from pathlib import Path

import nbformat
from nbclient import NotebookClient

PRELUDE = r"""
import cProfile
import functools
import io
import json
import pstats
import time
import tracemalloc
from pathlib import Path

_RECORD_PATH = Path(r"__RECORD_PATH__")
_PROFILE_PATH = Path(r"__PROFILE_PATH__")
_records = []
_profiler = cProfile.Profile()

from glotaran.optimization.optimization import Optimization
from glotaran.optimization.objective import OptimizationObjective
from glotaran.project.scheme import Scheme

_opt_run = Optimization.run
_opt_init = Optimization.__init__
_opt_dry = Optimization.dry_run
_obj_calculate = OptimizationObjective.calculate
_obj_calc_matrices = OptimizationObjective.calculate_matrices
_obj_calc_reduced = OptimizationObjective.calculate_reduced_matrices
_obj_calc_est = OptimizationObjective.calculate_estimations
_obj_get_result = OptimizationObjective.get_result

import glotaran.optimization.objective as _obj_mod
_add_svd = _obj_mod.add_svd_to_result_dataset

def _accumulate(name, start, extra=0.0):
    _records[-1].setdefault(name, 0.0)
    _records[-1][name] += time.perf_counter() - start - extra

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
        _accumulate("objective_total_s", start)
    return out

def _timed_calc_matrices(self):
    start = time.perf_counter()
    out = _obj_calc_matrices(self)
    if _records:
        _accumulate("matrices_s", start)
    return out

def _timed_calc_reduced(self, matrices):
    start = time.perf_counter()
    out = _obj_calc_reduced(self, matrices)
    if _records:
        _accumulate("reduce_s", start)
    return out

def _timed_calc_est(self, reduced):
    start = time.perf_counter()
    out = _obj_calc_est(self, reduced)
    if _records:
        _accumulate("estimations_s", start)
    return out

def _timed_add_svd(dataset, global_dim, model_dim):
    start = time.perf_counter()
    out = _add_svd(dataset, global_dim, model_dim)
    if _records:
        _accumulate("svd_s", start)
    return out

def _timed_get_result(self):
    start = time.perf_counter()
    out = _obj_get_result(self)
    if _records:
        _accumulate("get_result_s", start)
    return out

Optimization.__init__ = _timed_opt_init
OptimizationObjective.calculate = _timed_calculate
OptimizationObjective.calculate_matrices = _timed_calc_matrices
OptimizationObjective.calculate_reduced_matrices = _timed_calc_reduced
OptimizationObjective.calculate_estimations = _timed_calc_est
OptimizationObjective.get_result = _timed_get_result
_obj_mod.add_svd_to_result_dataset = _timed_add_svd

_scheme_optimize = Scheme.optimize

@functools.wraps(_scheme_optimize)
def _timed_scheme_optimize(self, *args, **kwargs):
    tracemalloc.start()
    _records.append({
        "dry_run": kwargs.get("dry_run", False),
        "max_nfev": kwargs.get("maximum_number_function_evaluations"),
    })
    start = time.perf_counter()
    _profiler.enable()
    try:
        result = _scheme_optimize(self, *args, **kwargs)
    finally:
        _profiler.disable()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    _records[-1]["total_s"] = time.perf_counter() - start
    _records[-1]["peak_traced_mb"] = peak / 1e6
    _RECORD_PATH.write_text(json.dumps(_records, indent=2))
    with _PROFILE_PATH.open("a", encoding="utf-8") as stream:
        stream.write(f"\n\n=== call {len(_records)} dry_run={kwargs.get('dry_run', False)} ===\n")
        stats = pstats.Stats(_profiler, stream=stream)
        stats.sort_stats("cumulative").print_stats(45)
        stats.sort_stats("tottime").print_stats(35)
    return result

Scheme.optimize = _timed_scheme_optimize
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--notebook", type=Path, required=True)
    parser.add_argument("--examples-root", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
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

    prelude = PRELUDE.replace("__RECORD_PATH__", str(output / "phase-records.json")).replace(
        "__PROFILE_PATH__", str(output / "profile.txt")
    )
    notebook.cells = [nbformat.v4.new_code_cell(source=prelude), *notebook.cells]

    NotebookClient(
        notebook,
        timeout=None,
        kernel_name="python3",
        resources={"metadata": {"path": str(source.parent)}},
        env=environment,
    ).execute()
    print(f"Profile records written to {output}")


if __name__ == "__main__":
    main()
