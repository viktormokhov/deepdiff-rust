"""Python package for the Rust-powered DeepDiff-compatible engine."""

from ._native import diff_json, version

__all__ = ["diff_json", "version"]
