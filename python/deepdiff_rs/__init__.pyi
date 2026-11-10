from collections.abc import Iterable
from re import Pattern
from typing import Any

__version__: str

class MaxDepthError(ValueError):
    """Raised when diffing two values would need to recurse past the configured ``max_depth``."""

MAX_DEPTH_CEILING: int

class DeepDiff(dict[str, Any]):
    """A drop-in ``deepdiff.DeepDiff``: the differences between ``t1`` and ``t2`` as a dict."""

    t1: Any
    t2: Any
    verbose_level: int

    def __init__(
        self,
        t1: Any,
        t2: Any,
        *,
        ignore_order: bool = ...,
        max_depth: int | None = ...,
        verbose_level: int = ...,
        view: str = ...,
        exclude_paths: str | Iterable[str] | None = ...,
        exclude_regex_paths: str | Pattern[str] | Iterable[str | Pattern[str]] | None = ...,
        include_paths: str | Iterable[str] | None = ...,
        exclude_types: Iterable[type] | None = ...,
        ignore_private_variables: bool = ...,
    ) -> None: ...
    def to_dict(self, verbose_level: int | None = ...) -> dict[str, Any]:
        """The differences as a plain dict, with ``type_changes`` types as type objects."""

    def to_json(
        self,
        default_mapping: dict[type, Any] | None = ...,
        force_use_builtin_json: bool = ...,
        verbose_level: int | None = ...,
        **kwargs: Any,
    ) -> str:
        """The differences as JSON; extra keyword arguments go to ``json.dumps``."""

    @property
    def affected_paths(self) -> set[str]:
        """The paths of every difference in this result."""

    @property
    def affected_root_keys(self) -> set[Any]:
        """The root keys, indices or attribute names the differences sit under."""

def diff_json(
    a: str,
    b: str,
    ignore_order: bool = ...,
    max_depth: int | None = ...,
) -> str:
    """Diffs two JSON documents and returns a ``DeepDiff``-compatible JSON report string (``verbose_level=2`` shape)."""

