"""DeepDiff result dict, drop-in for deepdiff.DeepDiff."""

import ast
import datetime
import decimal
import json
import uuid

from . import _native
from ._callbacks import callbacks_active, compose_skip
from ._dual import run_dual
from ._group_by import group_pair
from ._options import native_options
from ._paths import skip_filter
from ._delta import report_to_delta_dict
from ._view import build_tree, pretty_from_tree, tree_as_result

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


def _json_default(default_mapping):
    """DeepDiff-style `json.dumps` default: mapping first, then a small builtin fallback."""
    mapping = dict(default_mapping or ())

    def default(obj):
        for typ, convert in mapping.items():
            if isinstance(obj, typ):
                return convert(obj)
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, bytes):
            return list(obj)
        if isinstance(obj, type):
            return obj.__name__
        raise TypeError(
            f"Don't know how to JSON-serialize {obj!r} (type {type(obj).__name__}); "
            "consider adding it to default_mapping."
        )

    return default


def _root_key(path):
    rest = path[len("root"):]
    if rest.startswith("."):
        ends = [i for i in (rest.find(".", 1), rest.find("[")) if i > 0]
        return rest[1 : min(ends, default=len(rest))]
    end = rest.find("]")
    while end != -1:
        try:
            return ast.literal_eval(rest[1:end])
        except (ValueError, SyntaxError):
            end = rest.find("]", end + 1)
    return _NOT_PRESENT


class DeepDiff(dict):

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
        group_by=None, group_by_sort_key=None, report_repetition=False, max_diffs=None,
        max_passes=10000000, custom_operators=None, exclude_obj_callback=None,
        exclude_obj_callback_strict=None, include_obj_callback=None,
        include_obj_callback_strict=None, iterable_compare_func=None,
    ):
        if view not in ("text", "tree"):
            raise NotImplementedError(
                f"view={view!r} is not supported yet; only view='text' and view='tree' are."
            )
        self.view = view
        self.verbose_level = _check_verbose_level(verbose_level)
        self.ignore_order = ignore_order
        self.report_repetition = report_repetition
        self.group_by = group_by
        if not 0 <= float(cutoff_distance_for_pairs) <= 1:
            raise ValueError("cutoff_distance_for_pairs needs to be a positive float max 1.")
        if t1 is t2 and group_by is None:
            self.t1 = t1
            self.t2 = t2
            self._native = None
            self.tree = {}
            super().__init__()
            return
        t1, t2 = group_pair(t1, t2, group_by, group_by_sort_key)
        self.t1 = t1
        self.t2 = t2
        self.custom_operators = custom_operators or []
        self.exclude_obj_callback = exclude_obj_callback
        self.exclude_obj_callback_strict = exclude_obj_callback_strict
        self.include_obj_callback = include_obj_callback
        self.include_obj_callback_strict = include_obj_callback_strict
        self.iterable_compare_func = iterable_compare_func
        self._callbacks_active = callbacks_active(
            custom_operators=custom_operators,
            exclude_obj_callback=exclude_obj_callback,
            exclude_obj_callback_strict=exclude_obj_callback_strict,
            include_obj_callback=include_obj_callback,
            include_obj_callback_strict=include_obj_callback_strict,
            iterable_compare_func=iterable_compare_func,
        )
        exclude_types = tuple(exclude_types) if exclude_types else None
        if custom_operators or iterable_compare_func:
            def native_factory(a, b):
                return dict(
                    _native.DeepDiff(
                        a, b,
                        ignore_order=ignore_order, max_depth=max_depth,
                        exclude_types=exclude_types,
                        ignore_private_variables=ignore_private_variables,
                        use_enum_value=use_enum_value,
                        threshold_to_diff_deeper=float(threshold_to_diff_deeper or 0),
                        cutoff_distance_for_pairs=float(cutoff_distance_for_pairs),
                        cutoff_intersection_for_pairs=float(cutoff_intersection_for_pairs),
                        zip_ordered_iterables=zip_ordered_iterables,
                        get_deep_distance=False, report_repetition=report_repetition,
                        max_diffs=max_diffs, max_passes=max_passes,
                        **native_options(
                            _BUILTIN_TYPES, significant_digits=significant_digits,
                            number_format_notation=number_format_notation,
                            math_epsilon=math_epsilon, use_log_scale=use_log_scale,
                            log_scale_similarity_threshold=log_scale_similarity_threshold,
                            ignore_nan_inequality=ignore_nan_inequality,
                            ignore_string_case=ignore_string_case,
                            ignore_numeric_type_changes=ignore_numeric_type_changes,
                            ignore_string_type_changes=ignore_string_type_changes,
                            ignore_type_in_groups=ignore_type_in_groups,
                            ignore_type_subclasses=ignore_type_subclasses,
                            truncate_datetime=truncate_datetime,
                            ignore_uuid_types=ignore_uuid_types,
                        ),
                    ).to_dict(verbose_level)
                )
            self._native = None
            self._finish_init(run_dual(self, t1, t2, native_factory))
            return
        skip = skip_filter(exclude_paths, include_paths, exclude_regex_paths, exclude_types)
        skip = compose_skip(
            skip, t1, t2,
            exclude_obj_callback=exclude_obj_callback,
            exclude_obj_callback_strict=exclude_obj_callback_strict,
            include_obj_callback=include_obj_callback,
            include_obj_callback_strict=include_obj_callback_strict,
        )
        self._native = _native.DeepDiff(
            t1, t2, ignore_order=ignore_order, max_depth=max_depth, exclude_types=exclude_types,
            ignore_private_variables=ignore_private_variables, skip=skip, use_enum_value=use_enum_value,
            threshold_to_diff_deeper=float(threshold_to_diff_deeper or 0),
            cutoff_distance_for_pairs=float(cutoff_distance_for_pairs),
            cutoff_intersection_for_pairs=float(cutoff_intersection_for_pairs),
            zip_ordered_iterables=zip_ordered_iterables, get_deep_distance=get_deep_distance,
            report_repetition=report_repetition, max_diffs=max_diffs, max_passes=max_passes,
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
        self._finish_init(self.to_dict())

    def _finish_init(self, report):
        text = dict(report)
        self.tree = build_tree(text)
        if self.view == "tree":
            super().__init__(tree_as_result(self.tree))
        else:
            super().__init__(text)

    def _to_delta_dict(self, directed=True, always_include_values=False, report_repetition_required=True):
        if self.group_by is not None:
            raise ValueError(
                "Delta does not support group_by; recreate the DeepDiff without group_by."
            )
        if (
            report_repetition_required
            and self.ignore_order
            and not self.report_repetition
        ):
            raise ValueError(
                "When ignore_order is True, report_repetition must also be True for Delta."
            )
        return report_to_delta_dict(
            self.to_dict(verbose_level=2),
            directed=directed,
            always_include_values=always_include_values,
            ignore_order=self.ignore_order,
        )

    def to_dict(self, verbose_level=None):
        if self._native is None:
            if getattr(self, "view", "text") == "tree":
                out = {}
                for key, levels in self.tree.items():
                    if key.endswith(("_added", "_removed")) and self._level(verbose_level) < 2:
                        out[key] = [level.path() for level in levels]
                    elif key in ("values_changed", "type_changes"):
                        out[key] = {
                            level.path(): {
                                "old_value": level.t1,
                                "new_value": level.t2,
                                **(
                                    {"old_type": type(level.t1), "new_type": type(level.t2)}
                                    if key == "type_changes"
                                    else {}
                                ),
                            }
                            for level in levels
                        }
                    else:
                        out[key] = {
                            level.path(): level.t2 if key.endswith("_added") else level.t1
                            for level in levels
                        }
                return out
            return dict(self)
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
        if default_mapping is not None or force_use_builtin_json:
            return json.dumps(
                self.to_dict(verbose_level),
                default=_json_default(default_mapping),
                **kwargs,
            )
        if self._native is None:
            data = self.to_dict(verbose_level)
            return json.dumps(data, default=_json_default(None), **kwargs) if kwargs else json.dumps(
                data, default=_json_default(None)
            )
        text = self._native.to_json(self._level(verbose_level))
        if self._native.deep_distance is not None:
            report = json.loads(text)
            report["deep_distance"] = self._native.deep_distance
            return json.dumps(report, **kwargs)
        return json.dumps(json.loads(text), **kwargs) if kwargs else text

    @property
    def affected_paths(self):
        paths = set()
        for key, findings in self.items():
            if key == "deep_distance":
                continue
            if getattr(self, "view", "text") == "tree":
                paths.update(level.path() for level in findings)
            elif isinstance(findings, dict):
                paths.update(findings)
            else:
                paths.update(findings)
        return paths

    @property
    def affected_root_keys(self):
        report = self.to_dict(2)
        keys = set()
        for findings in report.values():
            if isinstance(findings, dict):
                keys.update(_root_key(path) for path in findings)
            else:
                keys.update(_root_key(path) for path in findings)
        keys.discard(_NOT_PRESENT)
        return keys

    def pretty(self, prefix=None):
        tree = getattr(self, "tree", None) or build_tree(self.to_dict())
        return pretty_from_tree(tree, self.verbose_level, prefix)

    def custom_report_result(self, report_type, level, extra_info=None):
        path = level.path()
        payload = dict(extra_info or {})
        if report_type == "values_changed":
            payload.setdefault("old_value", level.t1)
            payload.setdefault("new_value", level.t2)
        bucket = getattr(self, "_walk_report", self).setdefault(report_type, {})
        bucket[path] = payload
        if self._native is None:
            self.setdefault(report_type, {})[path] = payload

    def _report_result(self, report_type, change_level, local_tree=None):
        self.custom_report_result(report_type, change_level)

    def _level(self, verbose_level):
        return self.verbose_level if verbose_level is None else _check_verbose_level(verbose_level)
