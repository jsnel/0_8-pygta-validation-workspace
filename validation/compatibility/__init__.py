"""External semantic views for comparing the pinned pyglotaran result formats."""

from .load_v07 import load_v07_result
from .load_v08 import load_v08_result
from .schema import DatasetView, ResultView

__all__ = ["DatasetView", "ResultView", "load_v07_result", "load_v08_result"]
