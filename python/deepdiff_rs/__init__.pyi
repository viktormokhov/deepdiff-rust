from typing import Any

__version__: str

class MaxDepthError(ValueError):
    """Raised when diffing two values would need to recurse past the configured ``max_depth``."""

MAX_DEPTH_CEILING: int

class DeepDiff:
    """A drop-in subset of ``deepdiff.DeepDiff``, diffing ``t1``/``t2`` at ``verbose_level=2``."""

    def __init__(
        self,
        t1: Any,
        t2: Any,
        ignore_order: bool = ...,
        max_depth: int | None = ...,
    ) -> None: ...
    def to_json(self) -> str:
        """The report as a ``DeepDiff``-compatible JSON string at ``verbose_level=2``; a deep report renders on the sized worker thread rather than inline."""

    def to_dict(self) -> dict[str, Any]:
        """The report as a native Python dict, Python types (tuples, sets, datetimes) intact."""

    def __bool__(self) -> bool: ...
    def __repr__(self) -> str: ...

def diff_json(
    a: str,
    b: str,
    ignore_order: bool = ...,
    max_depth: int | None = ...,
) -> str:
    """Diffs two JSON documents and returns a ``DeepDiff``-compatible JSON report string (``verbose_level=2`` shape)."""

