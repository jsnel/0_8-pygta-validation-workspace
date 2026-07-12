"""Kernel-side timing hooks for the validation runtime benchmark.

This module is intentionally independent of the result-comparison layer. It is
imported by an in-memory notebook prelude and writes one small JSON file after
each public fit call so partial failures remain diagnosable.
"""

from __future__ import annotations

import functools
import importlib
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any


_STATE: dict[str, Any] | None = None


def _attribute_or_mapping(value: Any, name: str) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _first_value(values: list[Any], name: str) -> Any:
    for value in values:
        candidate = _attribute_or_mapping(value, name)
        if candidate is not None:
            if isinstance(candidate, (str, int, float, bool)) or candidate is None:
                return candidate
            return str(candidate)
    return None


def _workload(args: tuple[Any, ...], kwargs: dict[str, Any], result: Any) -> dict[str, Any]:
    scheme = args[0] if args else None
    info = _attribute_or_mapping(result, "optimization_info")
    optimization_result = _attribute_or_mapping(result, "optimization_result")
    candidates = [result, info, optimization_result, scheme]
    fields = (
        "number_of_function_evaluations",
        "number_of_jacobian_evaluations",
        "number_of_free_parameters",
        "number_of_parameters",
        "optimization_method",
        "maximum_number_function_evaluations",
    )
    metadata = {field: _first_value(candidates, field) for field in fields}
    for field in fields:
        if metadata[field] is None and field in kwargs:
            metadata[field] = kwargs[field]
    return metadata


def _write_records() -> None:
    if _STATE is None:
        return
    path = Path(_STATE["record_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(_STATE["records"], indent=2), encoding="utf-8")
    temporary.replace(path)


def _invoke(original: Any, entrypoint: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    assert _STATE is not None
    invocation = len(_STATE["records"]) + 1
    started = time.perf_counter_ns()
    try:
        result = original(*args, **kwargs)
    except BaseException as error:
        finished = time.perf_counter_ns()
        _STATE["records"].append(
            {
                "invocation": invocation,
                "entrypoint": entrypoint,
                "started_ns": started,
                "finished_ns": finished,
                "duration_ns": finished - started,
                "duration_seconds": (finished - started) / 1_000_000_000,
                "success": False,
                "error": repr(error),
                "exception_type": type(error).__name__,
                "workload": _workload(args, kwargs, None),
            }
        )
        _write_records()
        raise
    finished = time.perf_counter_ns()
    _STATE["records"].append(
        {
            "invocation": invocation,
            "entrypoint": entrypoint,
            "started_ns": started,
            "finished_ns": finished,
            "duration_ns": finished - started,
            "duration_seconds": (finished - started) / 1_000_000_000,
            "success": True,
            "error": None,
            "exception_type": None,
            "workload": _workload(args, kwargs, result),
        }
    )
    _write_records()
    return result


def install(branch: str, record_path: str) -> None:
    """Patch the branch's public fit entrypoint inside the notebook kernel."""

    global _STATE
    if _STATE is not None:
        return
    _STATE = {
        "branch": branch,
        "record_path": record_path,
        "records": [],
        "python": sys.version,
        "platform": platform.platform(),
        "thread_environment": {
            name: os.environ.get(name)
            for name in (
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "NUMBA_NUM_THREADS",
            )
        },
    }
    if branch == "main":
        module = importlib.import_module("glotaran.optimization.optimize")
        original = module.optimize

        @functools.wraps(original)
        def timed(*args: Any, **kwargs: Any) -> Any:
            return _invoke(original, "glotaran.optimization.optimize.optimize", args, kwargs)

        module.optimize = timed
    elif branch == "staging":
        module = importlib.import_module("glotaran.project.scheme")
        scheme_class = module.Scheme
        original = scheme_class.optimize

        @functools.wraps(original)
        def timed(self: Any, *args: Any, **kwargs: Any) -> Any:
            return _invoke(original, "glotaran.project.scheme.Scheme.optimize", (self, *args), kwargs)

        scheme_class.optimize = timed
    else:
        raise ValueError(f"Unknown benchmark branch: {branch}")

