from __future__ import annotations

from pygta_local_extras.io import apply_factor
from pygta_local_extras.io import ascii_folder_to_datasets_weight_coarsen_poisson
from pygta_local_extras.io import ascii_trace_folder_to_dataset_IRF
from pygta_local_extras.io import copy_irf_shape_parameters_to_file
from pygta_local_extras.io import copy_shift_conv_parameters_to_file
from pygta_local_extras.io import csv_to_dataset_IRF
from pygta_local_extras.io import csv_to_dataset_weight
from pygta_local_extras.io import csv_to_dataset_weight_coarsen
from pygta_local_extras.io import csv_to_dataset_weight_coarsen_poisson
from pygta_local_extras.io import free_shift_conv_parameters_to_file
from pygta_local_extras.io import freeze_shift_conv_parameters_to_file
from pygta_local_extras.io import irf_dataset_coarsen
from pygta_local_extras.io import reanchor_conv_multi_multi_gaussian_irf_parameters


def test_irf_loaders_are_exported_from_io() -> None:
    assert callable(ascii_trace_folder_to_dataset_IRF)
    assert callable(ascii_folder_to_datasets_weight_coarsen_poisson)
    assert callable(csv_to_dataset_IRF)
    assert callable(csv_to_dataset_weight)
    assert callable(csv_to_dataset_weight_coarsen)
    assert callable(csv_to_dataset_weight_coarsen_poisson)
    assert callable(apply_factor)
    assert callable(irf_dataset_coarsen)
    assert callable(copy_irf_shape_parameters_to_file)
    assert callable(copy_shift_conv_parameters_to_file)
    assert callable(free_shift_conv_parameters_to_file)
    assert callable(freeze_shift_conv_parameters_to_file)
    assert callable(reanchor_conv_multi_multi_gaussian_irf_parameters)
