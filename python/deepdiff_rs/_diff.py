"""The `DeepDiff` result: a `dict` of findings, like `deepdiff.DeepDiff`."""

import ast
import datetime
import decimal
import json
import uuid

from . import _native
from ._group_by import group_pair
from ._options import native_options
from ._paths import skip_filter

_BUILTIN_TYPES = {
    t.__name__: t
    for t in (
        type(None), bool, int, float, str, list, tuple, set, frozenset, dict,
        datetime.datetime, datetime.date, datetime.time, datetime.timedelta,
        bytes, complex, decimal.Decimal, uuid.UUID,
    )
}


def _check_verbose_level(verbose_level):
    if verbose_level not in (0, 1, 2):
        raise ValueError("verbose_level should be 0, 1, or 2.")
    return verbose_level


_NOT_PRESENT = object()


def _root_key(path):
    """The key, index or attribute name right after `root` in a rendered path."""
    rest = path[len("root"):]
    if rest.startswith("."):
        ends = [i for i in (rest.find(".", 1), rest.find("[")) if i > 0]
        return rest[1 : min(ends, default=len(rest))]
    # ponytail: tries each "]" until the key parses as a literal; a key whose
    # repr is not a Python literal is skipped.
    end = rest.find("]")
    while end != -1:
        try:
            return ast.literal_eval(rest[1:end])
        except (ValueError, SyntaxError):
            end = rest.find("]", end + 1)
    return _NOT_PRESENT


class DeepDiff(dict):
    """A drop-in `deepdiff.DeepDiff`: the differences between `t1` and `t2` as a dict."""

    def __init__(
        self, t1, t2, *, ignore_order=False, max_depth=None, verbose_level=1, view="text",
        exclude_paths=None, exclude_regex_paths=None, include_paths=None, exclude_types=None,
        ignore_private_variables=True, significant_digits=None, number_format_notation="f",
        math_epsilon=None, use_log_scale=False, log_scale_similarity_threshold=0.1,
        ignore_nan_inequality=False, ignore_string_case=False, ignore_numeric_type_changes=False,
        ignore_string_type_changes=False, ignore_type_in_groups=None, ignore_type_subclasses=False,
        truncate_datetime=None, ignore_uuid_types=False, use_enum_value=False,
        threshold_to_diff_deeper=0.33, cutoff_distance_for_pairs=0.3,
        cutoff_intersection_for_pairs=0.7, zip_ordered_iterables=False, get_deep_distance=False,
        group_by=None, group_by_sort_key=None,
    ):
        if view != "text":
            raise NotImplementedError(f"view={view!r} is not supported yet; only view='text' is.")
        self.verbose_level = _check_verbose_level(verbose_level)
        if not 0 <= float(cutoff_distance_for_pairs) <= 1:
            raise ValueError("cutoff_distance_for_pairs needs to be a positive float max 1.")
        t1, t2 = group_pair(t1, t2, group_by, group_by_sort_key)
        self.t1 = t1
        self.t2 = t2
        exclude_types = tuple(exclude_types) if exclude_types else None
        skip = skip_filter(exclude_paths, include_paths, exclude_regex_paths, exclude_types)
        self._native = _native.DeepDiff(
            t1, t2, ignore_order=ignore_order, max_depth=max_depth, exclude_types=exclude_types,
            ignore_private_variables=ignore_private_variables, skip=skip, use_enum_value=use_enum_value,
            threshold_to_diff_deeper=float(threshold_to_diff_deeper or 0),
            cutoff_distance_for_pairs=float(cutoff_distance_for_pairs),
            cutoff_intersection_for_pairs=float(cutoff_intersection_for_pairs),
            zip_ordered_iterables=zip_ordered_iterables, get_deep_distance=get_deep_distance,
            **native_options(
                _BUILTIN_TYPES, significant_digits=significant_digits,
                number_format_notation=number_format_notation, math_epsilon=math_epsilon,
                use_log_scale=use_log_scale,
                log_scale_similarity_threshold=log_scale_similarity_threshold,
                ignore_nan_inequality=ignore_nan_inequality, ignore_string_case=ignore_string_case,
                ignore_numeric_type_changes=ignore_numeric_type_changes,
                ignore_string_type_changes=ignore_string_type_changes,
                ignore_type_in_groups=ignore_type_in_groups,
                ignore_type_subclasses=ignore_type_subclasses,
                truncate_datetime=truncate_datetime, ignore_uuid_types=ignore_uuid_types,
            ),
        )
        super().__init__(self.to_dict())

    def to_dict(self, verbose_level=None):
        """The differences as a plain dict, with `type_changes` types as type objects."""
        report = self._native.to_dict(self._level(verbose_level))
        if "type_changes" in report:
            classes = {**_BUILTIN_TYPES, **self._native._types}
            for change in report["type_changes"].values():
                for key in ("old_type", "new_type"):
                    change[key] = classes.get(change[key], change[key])
        if self._native.deep_distance is not None:
            report["deep_distance"] = self._native.deep_distance
        return report

    def to_json(self, default_mapping=None, force_use_builtin_json=False, verbose_level=None, **kwargs):
        """The differences as JSON; extra keyword arguments go to `json.dumps`."""
        if default_mapping is not None:
            raise NotImplementedError("default_mapping is not supported yet.")
        text = self._native.to_json(self._level(verbose_level))
        if self._native.deep_distance is not None:
            report = json.loads(text)
            report["deep_distance"] = self._native.deep_distance
            return json.dumps(report, **kwargs)
        return json.dumps(json.loads(text), **kwargs) if kwargs else text

    @property
    def affected_paths(self):
        """The paths of every difference in this result."""
        return {path for key, findings in self.items() if key != "deep_distance" for path in findings}

    @property
    def affected_root_keys(self):
        """The root keys, indices or attribute names the differences sit under."""
        keys = {_root_key(path) for findings in self._native.to_dict(2).values() for path in findings}
        keys.discard(_NOT_PRESENT)
        return keys

    def _level(self, verbose_level):
        return self.verbose_level if verbose_level is None else _check_verbose_level(verbose_level)
