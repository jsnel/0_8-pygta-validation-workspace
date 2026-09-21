"""Tests for initial concentration inspection helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import xarray as xr
from pygta_local_extras.analysis import initial_concentration_table
from pygta_local_extras.analysis import selected_initial_concentration_table


def _make_a_matrix_dataset(
    *,
    megacomplexes: list[tuple[str, list[str], list[float]]],
) -> xr.Dataset:
    data_vars: dict[str, xr.DataArray] = {}
    for mc_label, species, initial_concentration in megacomplexes:
        component_name = f"component_{mc_label}"
        species_name = f"species_{mc_label}"
        size = len(species)
        data_vars[f"a_matrix_{mc_label}"] = xr.DataArray(
            np.eye(size),
            dims=(component_name, species_name),
            coords={
                component_name: np.arange(size),
                species_name: species,
                f"initial_concentration_{mc_label}": (species_name, initial_concentration),
                f"lifetime_{mc_label}": (component_name, np.ones(size)),
            },
        )
    return xr.Dataset(data_vars)


@dataclass
class _DummyParameter:
    value: float


@dataclass
class _DummyDatasetModel:
    megacomplex: list[str]
    megacomplex_scale: list[str] | None = None


@dataclass
class _DummyModel:
    dataset: dict[str, _DummyDatasetModel]


class _DummyParameters:
    def __init__(self, values: dict[str, float]):
        self._values = values

    def get(self, label: str) -> _DummyParameter:
        return _DummyParameter(self._values[label])


@dataclass
class _DummyResult:
    data: dict[str, xr.Dataset]
    model: _DummyModel
    optimized_parameters: _DummyParameters


def test_initial_concentration_table_collects_dataset_rows() -> None:
    result = {
        "open": _make_a_matrix_dataset(
            megacomplexes=[
                ("mc1", ["s1", "s5"], [95.0, 35.0]),
                ("mc2", ["s8"], [12.0]),
            ]
        ),
        "close": _make_a_matrix_dataset(
            megacomplexes=[
                ("mc1", ["s1", "s5"], [190.0, 70.0]),
            ]
        ),
    }

    table = initial_concentration_table(result)

    assert list(table.index) == ["open", "close"]
    assert list(table.columns) == ["s1", "s5", "s8"]
    assert table.loc["open", "s1"] == 95.0
    assert table.loc["open", "s5"] == 35.0
    assert table.loc["open", "s8"] == 12.0
    assert table.loc["close", "s1"] == 190.0
    assert table.loc["close", "s5"] == 70.0
    assert table.loc["close", "s8"] == 0.0


def test_initial_concentration_table_omits_species() -> None:
    result = {
        "open": _make_a_matrix_dataset(
            megacomplexes=[
                ("mc1", ["s1", "oscatfoo", "cscatfoo", "s5"], [95.0, 1.0, 2.0, 35.0]),
            ]
        ),
    }

    table = initial_concentration_table(result, omit=["oscatfoo", "cscatfoo"])

    assert list(table.columns) == ["s1", "s5"]
    assert table.loc["open", "s1"] == 95.0
    assert table.loc["open", "s5"] == 35.0


def test_selected_initial_concentration_table_applies_multipliers() -> None:
    result = {
        "open": _make_a_matrix_dataset(megacomplexes=[("mc1", ["s1", "s5"], [95.0, 35.0])]),
        "close": _make_a_matrix_dataset(megacomplexes=[("mc1", ["s1", "s5"], [190.0, 70.0])]),
    }

    table = selected_initial_concentration_table(
        result,
        ["s1", "s5"],
        multipliers={"s1": 1 / 95, "s5": 1 / 35},
    )

    assert list(table.columns) == ["s1", "s5"]
    assert table.loc["open", "s1"] == 1.0
    assert table.loc["open", "s5"] == 1.0
    assert table.loc["close", "s1"] == 2.0
    assert table.loc["close", "s5"] == 2.0


def test_selected_initial_concentration_table_passes_omit() -> None:
    result = {
        "open": _make_a_matrix_dataset(
            megacomplexes=[("mc1", ["s1", "oscatfoo", "s5"], [95.0, 1.0, 35.0])]
        ),
    }

    table = selected_initial_concentration_table(
        result,
        ["s1", "oscatfoo", "s5"],
        omit=["oscatfoo"],
    )

    assert list(table.columns) == ["s1", "oscatfoo", "s5"]
    assert table.loc["open", "s1"] == 95.0
    assert table.loc["open", "oscatfoo"] == 0.0
    assert table.loc["open", "s5"] == 35.0


def test_initial_concentration_table_applies_megacomplex_scale_from_result() -> None:
    result = _DummyResult(
        data={
            "state2": _make_a_matrix_dataset(
                megacomplexes=[
                    ("complex1", ["s1", "s2"], [100.0, 20.0]),
                    ("complex2", ["s1", "s2"], [5.0, 10.0]),
                ]
            ),
        },
        model=_DummyModel(
            dataset={
                "state2": _DummyDatasetModel(
                    megacomplex=["complex1", "complex2"],
                    megacomplex_scale=["scalem.state2.1", "scalem.state2.2"],
                )
            }
        ),
        optimized_parameters=_DummyParameters({"scalem.state2.1": 2.0, "scalem.state2.2": 3.0}),
    )

    table = initial_concentration_table(result)

    assert table.loc["state2", "s1"] == 215.0
    assert table.loc["state2", "s2"] == 70.0


def test_selected_initial_concentration_table_applies_megacomplex_scale_from_result() -> None:
    result = _DummyResult(
        data={
            "state2": _make_a_matrix_dataset(
                megacomplexes=[
                    ("complex1", ["s1", "s4"], [10.0, 30.0]),
                    ("complex2", ["s1", "s4"], [1.0, 2.0]),
                ]
            ),
        },
        model=_DummyModel(
            dataset={
                "state2": _DummyDatasetModel(
                    megacomplex=["complex1", "complex2"],
                    megacomplex_scale=["scalem.state2.1", "scalem.state2.2"],
                )
            }
        ),
        optimized_parameters=_DummyParameters({"scalem.state2.1": 4.0, "scalem.state2.2": 0.5}),
    )

    table = selected_initial_concentration_table(result, ["s1", "s4"])

    assert table.loc["state2", "s1"] == 40.5
    assert table.loc["state2", "s4"] == 121.0
