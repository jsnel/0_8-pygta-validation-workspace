"""Opt-in integration check using both installed validation environments."""

import os
from pathlib import Path
import subprocess

import numpy as np
import pytest


@pytest.mark.skipif(
    os.environ.get("PYGLOTARAN_RUN_SPECTRAL_PROBE") != "1",
    reason="Requires both local pyglotaran environments; explicitly opt in.",
)
def test_spectral_guidance_objective_and_trajectory_parity(tmp_path):
    """Match numerical runtime and compartment order, then compare both engines.

    This tests native objectives before result construction or compatibility
    conversion, including every finite-difference and trust-region evaluation.
    It does not assert equality of non-identifiable fitted parameters under
    different runtimes, nor reclassify the current-tree semantic regression.
    """
    root = Path(__file__).resolve().parents[2]
    for branch in ("main", "staging"):
        command = [
            str(root / f"temp/pyglotaran-{branch}-dev/.venv/Scripts/python.exe"),
            str(root / "validation/spectral_guidance_probe.py"),
            "--branch", branch,
            "--output", str(tmp_path / branch),
        ]
        if branch == "staging":
            command += [
                "--canonical-compartments",
                "--numeric-site",
                str(root / "temp/pyglotaran-main-dev/.venv/Lib/site-packages"),
            ]
        completed = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=120)
        assert completed.returncode == 0, completed.stdout + completed.stderr

    with np.load(tmp_path / "main/arrays.npz") as main, np.load(
        tmp_path / "staging/arrays.npz"
    ) as staging:
        for field in ("initial", "jac", "x", "residual"):
            np.testing.assert_array_equal(main[field], staging[field])
        # v0.7 additionally restores/evaluates the accepted vector for packaging.
        np.testing.assert_array_equal(main["call_x"][:-1], staging["call_x"])
        np.testing.assert_array_equal(main["call_residual"][:-1], staging["call_residual"])
