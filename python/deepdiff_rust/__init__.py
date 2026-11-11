"""Rust-backed DeepDiff-compatible comparison engine."""

from ._native import MAX_DEPTH_CEILING, MaxDepthError, __version__, diff_json
from ._delta import Delta, DeltaError, DeltaNumpyOperatorOverrideError
from ._diff import DeepDiff
from ._path import extract

__all__ = [
    "DeepDiff",
    "Delta",
    "DeltaError",
    "DeltaNumpyOperatorOverrideError",
    "diff_json",
    "extract",
    "MaxDepthError",
    "MAX_DEPTH_CEILING",
    "__version__",
]
