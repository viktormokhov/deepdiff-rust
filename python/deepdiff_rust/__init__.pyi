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
        significant_digits: int | None = ...,
        number_format_notation: str = ...,
        math_epsilon: float | None = ...,
        use_log_scale: bool = ...,
        log_scale_similarity_threshold: float = ...,
        ignore_nan_inequality: bool = ...,
        ignore_string_case: bool = ...,
        ignore_numeric_type_changes: bool = ...,
        ignore_string_type_changes: bool = ...,
        ignore_type_in_groups: Any = ...,
        ignore_type_subclasses: bool = ...,
        truncate_datetime: str | None = ...,
        ignore_uuid_types: bool = ...,
        use_enum_value: bool = ...,
        threshold_to_diff_deeper: float = ...,
        cutoff_distance_for_pairs: float = ...,
        cutoff_intersection_for_pairs: float = ...,
        zip_ordered_iterables: bool = ...,
        get_deep_distance: bool = ...,
        group_by: Any = ...,
        group_by_sort_key: Any = ...,
        report_repetition: bool = ...,
        max_diffs: int | None = ...,
        max_passes: int = ...,
        custom_operators: list[Any] | None = ...,
        exclude_obj_callback: Any | None = ...,
        exclude_obj_callback_strict: Any | None = ...,
        include_obj_callback: Any | None = ...,
        include_obj_callback_strict: Any | None = ...,
        iterable_compare_func: Any | None = ...,
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

