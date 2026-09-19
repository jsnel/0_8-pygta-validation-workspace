from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pygta_local_extras.analysis.pygta_result_processing as result_processing
import xarray as xr


def _dataset(spectral: list[float], scale_list: list[float]) -> xr.Dataset:
    time = [0.0, 1.0]
    data = np.arange(len(time) * len(spectral), dtype=float).reshape(len(time), -1)
    return xr.Dataset(
        {
            "data": (("time", "spectral"), data),
            "residual": (("time", "spectral"), data),
            "species_associated_spectra": (
                ("spectral", "species"),
                np.ones((len(spectral), 2)),
            ),
        },
        coords={"time": time, "spectral": spectral, "species": ["keep", "scatter"]},
        attrs={"dataset_scale_list": scale_list},
    )


def test_concatenate_result_datasets_preserves_scales_and_recomputes_svd(monkeypatch) -> None:
    result = SimpleNamespace(
        data={
            "first": _dataset([660.0], [2.0]),
            "second": _dataset([710.0, 711.0], [3.0, 4.0]),
        }
    )
    calls = []

    def fake_add_svd(dataset, label):
        calls.append(label)
        dataset["residual_right_singular_vectors"] = (
            ("right_singular_value_index", "spectral"),
            np.ones((1, dataset.sizes["spectral"])),
        )
        return dataset

    monkeypatch.setattr(result_processing, "add_svd", fake_add_svd)

    concatenated = result_processing.concatenate_result_datasets(
        result,
        ["first", "second"],
        ["scatter"],
    )

    assert concatenated.spectral.values.tolist() == [660.0, 710.0, 711.0]
    assert concatenated.attrs["dataset_scale_list"] == [2.0, 3.0, 4.0]
    assert concatenated.species.values.tolist() == ["keep"]
    assert "residual_right_singular_vectors" in concatenated
    assert calls == ["concatenated"]
