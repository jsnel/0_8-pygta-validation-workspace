"""Tests for pygta_local_extras.analysis.steady_state."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import xarray as xr
from pygta_local_extras.analysis.steady_state import _steady_state_concentrations_from_dataset
from pygta_local_extras.analysis.steady_state import compute_steady_state_spectra

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dataset(
    *,
    n_spectral: int = 5,
    species: list[str],
    rates: np.ndarray,
    a_matrix: np.ndarray,
    sas: np.ndarray,
    mc_label: str = "mc1",
) -> xr.Dataset:
    """Build a minimal xr.Dataset that looks like a pyglotaran result dataset."""
    spectral = np.linspace(600, 750, n_spectral)
    lifetimes = 1.0 / rates

    component_name = f"component_{mc_label}"
    species_name = f"species_{mc_label}"

    a_mat_da = xr.DataArray(
        a_matrix,  # (n_components, n_species)
        dims=(component_name, species_name),
        coords={
            component_name: np.arange(1, rates.size + 1),
            f"rate_{mc_label}": (component_name, rates),
            f"lifetime_{mc_label}": (component_name, lifetimes),
            species_name: species,
        },
    )

    sas_da = xr.DataArray(
        sas,  # (n_spectral, n_species)
        dims=("spectral", "species"),
        coords={"spectral": spectral, "species": species},
    )

    return xr.Dataset(
        {
            f"a_matrix_{mc_label}": a_mat_da,
            "species_associated_spectra": sas_da,
        }
    )


class _FakeResult:
    """Minimal duck-typed stand-in for a pyglotaran Result."""

    def __init__(self, data: dict[str, xr.Dataset]) -> None:
        self.data = data


# ---------------------------------------------------------------------------
# Unit tests: _steady_state_concentrations_from_dataset
# ---------------------------------------------------------------------------


def test_steady_state_concentrations_simple():
    """For a diagonal A-matrix, c_SS[i] = A[i,i] * tau[i]."""
    species = ["s1", "s2"]
    rates = np.array([1.0, 2.0])
    # Diagonal A: each component maps 1-to-1 to a species.
    a_matrix = np.diag([0.5, 0.8])  # (2, 2)
    sas = np.ones((5, 2))

    ds = _make_dataset(species=species, rates=rates, a_matrix=a_matrix, sas=sas)
    c_ss = _steady_state_concentrations_from_dataset(ds)

    assert set(c_ss.keys()) == {"s1", "s2"}
    # c_SS[i] = A[i,i] * tau[i]  (only diagonal term is non-zero here)
    np.testing.assert_allclose(c_ss["s1"], 0.5 * (1.0 / 1.0))
    np.testing.assert_allclose(c_ss["s2"], 0.8 * (1.0 / 2.0))


def test_steady_state_concentrations_no_a_matrix():
    """Dataset without an a_matrix variable returns an empty dict."""
    ds = xr.Dataset({"species_associated_spectra": xr.DataArray(np.ones((3, 2)))})
    assert _steady_state_concentrations_from_dataset(ds) == {}


# ---------------------------------------------------------------------------
# Unit tests: compute_steady_state_spectra
# ---------------------------------------------------------------------------


def test_compute_steady_state_spectra_values():
    """Verify end-to-end computation with a known two-species system."""
    species = ["s1", "s2"]
    rates = np.array([1.0, 2.0])
    # All amplitude goes to own component -> diagonal
    a_matrix = np.diag([1.0, 1.0])  # (n_components=2, n_species=2)

    rng = np.random.default_rng(42)
    sas = rng.random((5, 2))  # (n_spectral=5, n_species=2)

    ds = _make_dataset(species=species, rates=rates, a_matrix=a_matrix, sas=sas, n_spectral=5)
    result = _FakeResult({"ds1": ds})

    out = compute_steady_state_spectra(result)

    assert "ds1" in out
    ds_out = out["ds1"]
    assert "steady_state_spectra" in ds_out
    assert "steady_state_spectrum" in ds_out

    # c_SS = A.T @ tau = I @ [1, 0.5] = [1, 0.5]
    c_ss_expected = np.array([1.0, 0.5])
    expected_per_species = sas * c_ss_expected[np.newaxis, :]
    expected_total = expected_per_species.sum(axis=1)

    np.testing.assert_allclose(ds_out["steady_state_spectra"].values, expected_per_species)
    np.testing.assert_allclose(ds_out["steady_state_spectrum"].values, expected_total)


def test_compute_steady_state_spectra_dims():
    """Output DataArrays carry correct dimension names."""
    species = ["s1", "s2", "s3"]
    rates = np.array([0.5, 1.0, 4.0])
    a_matrix = np.eye(3)
    sas = np.ones((8, 3))

    ds = _make_dataset(species=species, rates=rates, a_matrix=a_matrix, sas=sas, n_spectral=8)
    result = _FakeResult({"d": ds})
    out = compute_steady_state_spectra(result)["d"]

    assert out["steady_state_spectra"].dims == ("spectral", "species")
    assert out["steady_state_spectrum"].dims == ("spectral",)
    assert list(out["steady_state_spectra"].coords["species"].values) == species


def test_compute_steady_state_spectra_skips_dataset_without_a_matrix():
    """Datasets lacking an a_matrix are silently excluded from the output."""
    ds = xr.Dataset({"species_associated_spectra": xr.DataArray(np.ones((3, 2)))})
    result = _FakeResult({"no_a": ds})
    out = compute_steady_state_spectra(result)
    assert out == {}


def test_compute_steady_state_spectra_multi_megacomplex():
    """Two megacomplexes on the same dataset accumulate their contributions."""
    species = ["s1", "s2"]
    rates1 = np.array([1.0])
    rates2 = np.array([2.0])

    # mc1: component 1 -> s1 only
    a1 = np.array([[0.6, 0.0]])  # (1 component, 2 species)
    # mc2: component 1 -> s2 only
    a2 = np.array([[0.0, 0.4]])  # (1 component, 2 species)

    sas_vals = np.ones((4, 2))
    spectral = np.linspace(600, 750, 4)

    def _a_da(a, rates, mc_label):
        c_name = f"component_{mc_label}"
        s_name = f"species_{mc_label}"
        return xr.DataArray(
            a,
            dims=(c_name, s_name),
            coords={
                c_name: np.arange(1, rates.size + 1),
                f"lifetime_{mc_label}": (c_name, 1.0 / rates),
                f"rate_{mc_label}": (c_name, rates),
                s_name: species,
            },
        )

    sas_da = xr.DataArray(
        sas_vals,
        dims=("spectral", "species"),
        coords={"spectral": spectral, "species": species},
    )
    ds = xr.Dataset(
        {
            "a_matrix_mc1": _a_da(a1, rates1, "mc1"),
            "a_matrix_mc2": _a_da(a2, rates2, "mc2"),
            "species_associated_spectra": sas_da,
        }
    )

    result = _FakeResult({"d": ds})
    out = compute_steady_state_spectra(result)["d"]

    # c_SS[s1] = 0.6 * (1/1) + 0   = 0.6
    # c_SS[s2] = 0   + 0.4 * (1/2) = 0.2
    np.testing.assert_allclose(
        out["steady_state_spectra"].sel(species="s1").values,
        np.full(4, 0.6),
    )
    np.testing.assert_allclose(
        out["steady_state_spectra"].sel(species="s2").values,
        np.full(4, 0.2),
    )
    np.testing.assert_allclose(
        out["steady_state_spectrum"].values,
        np.full(4, 0.8),
    )


def test_compute_steady_state_spectra_applies_megacomplex_scales():
    """Megacomplex scale parameters multiply their steady-state contribution."""
    ds = _make_dataset(
        species=["s1", "s2"],
        rates=np.array([1.0, 2.0]),
        a_matrix=np.diag([0.5, 0.0]),
        sas=np.ones((3, 2)),
        mc_label="complex1",
        n_spectral=3,
    )

    class _Parameters:
        def get(self, label):
            return SimpleNamespace(value={"scale.1": 2.0}[label])

    result = SimpleNamespace(
        data={"state2": ds},
        model=SimpleNamespace(
            dataset={
                "state2": SimpleNamespace(
                    megacomplex=["complex1"],
                    megacomplex_scale=["scale.1"],
                )
            }
        ),
        optimized_parameters=_Parameters(),
    )

    out = compute_steady_state_spectra(result)["state2"]

    # A.T @ lifetime gives 0.5; the megacomplex scale makes it 1.0.
    np.testing.assert_allclose(out["steady_state_spectrum"].values, np.ones(3))


def test_compute_steady_state_spectra_exclude_species():
    """Excluded species do not appear in the output dataset."""
    species = ["s1", "scatter"]
    rates = np.array([1.0, 100.0])
    a_matrix = np.diag([1.0, 5.0])  # scatter has high amplitude
    sas = np.ones((5, 2))

    ds = _make_dataset(species=species, rates=rates, a_matrix=a_matrix, sas=sas, n_spectral=5)
    result = _FakeResult({"d": ds})
    out = compute_steady_state_spectra(result, exclude_species=["scatter"])["d"]

    # Only s1 should remain.
    assert list(out["steady_state_spectra"].coords["species"].values) == ["s1"]
    # steady_state_spectrum = c_SS[s1] * SAS_s1 = 1.0 * 1.0 = 1.0 everywhere
    np.testing.assert_allclose(out["steady_state_spectrum"].values, np.ones(5))


def test_compute_steady_state_spectra_exclude_absent_species_is_noop():
    """Excluding a species that does not exist in a dataset is silently ignored."""
    species = ["s1", "s2"]
    rates = np.array([1.0, 2.0])
    a_matrix = np.diag([1.0, 1.0])
    sas = np.ones((5, 2))

    ds = _make_dataset(species=species, rates=rates, a_matrix=a_matrix, sas=sas, n_spectral=5)
    result = _FakeResult({"d": ds})

    # "nonexistent" is not in the dataset; result should be identical to the
    # call without exclude_species.
    out_filtered = compute_steady_state_spectra(result, exclude_species=["nonexistent"])["d"]
    out_unfiltered = compute_steady_state_spectra(result)["d"]

    np.testing.assert_allclose(
        out_filtered["steady_state_spectrum"].values,
        out_unfiltered["steady_state_spectrum"].values,
    )
