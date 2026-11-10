"""Rust-backed DeepDiff-compatible comparison engine."""

from ._native import MAX_DEPTH_CEILING, MaxDepthError, __version__, diff_json
from ._diff import DeepDiff

__all__ = ["DeepDiff", "diff_json", "MaxDepthError", "MAX_DEPTH_CEILING", "__version__"]
