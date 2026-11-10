"""Rust-backed DeepDiff-compatible comparison engine."""

from ._native import MAX_DEPTH_CEILING, MaxDepthError, DeepDiff, diff_json

__all__ = ["DeepDiff", "diff_json", "MaxDepthError", "MAX_DEPTH_CEILING"]
