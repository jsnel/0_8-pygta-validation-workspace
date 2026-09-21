"""Selection and slicing helpers for local pygta workflows."""

from pygta_local_extras.selection.ranges import slice_by_ranges
from pygta_local_extras.selection.ranges import slice_data_by_spectral_range
from pygta_local_extras.selection.ranges import slice_data_by_time_range
from pygta_local_extras.selection.ranges import slice_spectral_range
from pygta_local_extras.selection.ranges import slice_time_range

__all__ = [
    "slice_by_ranges",
    "slice_data_by_spectral_range",
    "slice_data_by_time_range",
    "slice_spectral_range",
    "slice_time_range",
]
