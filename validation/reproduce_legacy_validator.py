"""Run the historical validator against explicit result roots.

The upstream legacy action discovers the reference tree from a checkout and the
current tree from ``Path.home()``/``GITHUB_WORKSPACE``.  That is convenient in
CI, but it makes a local reproduction fetch and reset the gold-standard branch
and makes it difficult to select a particular pair of artifacts.  This harness
loads the test module once, replaces both path selectors before collection, and
then asks pytest to run that loaded module.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from types import ModuleType

import pytest


def load_validator(
    validator_path: Path,
    reference_root: Path,
    current_root: Path,
) -> ModuleType:
    """Load the legacy test module with both result roots explicitly bound."""

    module_name = "test_result_consistency"
    source = validator_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(validator_path))
    # The old module defines these selectors itself.  Remove those two
    # definitions before execution, leaving our explicit selectors in place
    # while retaining the validator's import-time parametrization.
    tree.body = [
        node
        for node in tree.body
        if not (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in {"get_compare_results_path", "get_current_result_path"}
        )
    ]
    module = ModuleType(module_name)
    module.__file__ = str(validator_path)
    module.__package__ = ""
    # pytest imports the file by its stem.  Registering the same module first
    # lets collection reuse this already-patched instance instead of executing
    # it a second time with its network-backed path selectors.
    sys.modules[module_name] = module
    module.get_compare_results_path = lambda: reference_root  # type: ignore[attr-defined]
    module.get_current_result_path = lambda: current_root  # type: ignore[attr-defined]
    exec(compile(tree, str(validator_path), "exec"), module.__dict__)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validator", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--current-root", type=Path, required=True)
    args = parser.parse_args()

    validator = args.validator.resolve()
    reference_root = args.reference_root.resolve()
    current_root = args.current_root.resolve()
    for label, path in (
        ("validator", validator),
        ("reference root", reference_root),
        ("current root", current_root),
    ):
        if not path.exists():
            parser.error(f"{label} does not exist: {path}")

    module = load_validator(validator, reference_root, current_root)

    return pytest.main(["-ra", str(validator)])


if __name__ == "__main__":
    raise SystemExit(main())
