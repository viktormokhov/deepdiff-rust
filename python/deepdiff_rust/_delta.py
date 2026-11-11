"""Delta / patch — apply a DeepDiff report to an object (scope: no pickle/flat)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from copy import deepcopy
from functools import cmp_to_key
from numbers import Number

from ._path import (
    GET,
    GETATTR,
    check_elem,
    get_nested_obj,
    get_nested_obj_and_force,
    parent_path_and_member,
    path_to_elements,
)

logger = logging.getLogger(__name__)

_NOT_FOUND = object()
_DELTA_AT_LEAST_ONE = "At least one of the diff or delta_diff arguments need to be passed."
_VERIFICATION = (
    "Expected the old value for {} to be {} but it is {}. Error found on: {}. "
    "You may want to set force=True."
)
_VERIFY_BI = (
    "You have applied the delta to an object that has "
    "different values than the original object the delta was made from."
)
_TYPE_CHANGE_FAIL = "Unable to do the type change for {} from to type {} due to {}"
_ELEM_NOT_FOUND = "Key or index of {} is not found for {} for setting operation."
_UNABLE_GET = "Unable to get the item at {}: {}"
_UNABLE_PATH = "Unable to get the item at {}"
_NUMPY_ADD = (
    "A numpy ndarray is most likely being added to a delta. "
    "Due to Numpy override the + operator, you can only do: delta + ndarray "
    "and NOT ndarray + delta"
)


class DeltaError(ValueError):
    """Delta-specific errors."""


class DeltaNumpyOperatorOverrideError(ValueError):
    """Raised when numpy's `+` would reverse operand order incorrectly."""


def _deserialize_diff(payload, deserializer, safe_to_import):
    """Turn a str/bytes delta payload into a mapping via ``deserializer``."""
    if deserializer is None:
        raise NotImplementedError(
            "string/bytes diff requires deserializer=... "
            "(pickle default is not bundled; pass json.loads or another callable)"
        )
    # DeepDiff's pickle_load accepts safe_to_import=; json.loads does not.
    accepts_safe = False
    code = getattr(deserializer, "__code__", None)
    if code is not None and "safe_to_import" in code.co_varnames:
        accepts_safe = True
    result = (
        deserializer(payload, safe_to_import=safe_to_import)
        if accepts_safe
        else deserializer(payload)
    )
    if not isinstance(result, Mapping):
        raise TypeError(
            f"deserializer must return a mapping, got {type(result).__name__}"
        )
    return result


def report_to_delta_dict(report, *, directed=True, always_include_values=False, ignore_order=False):
    """Reshape a text DeepDiff report into a Delta-compatible dictionary."""
    result = deepcopy(dict(report))
    result.pop("deep_distance", None)

    for key in ("set_item_added", "set_item_removed"):
        items = result.get(key)
        if isinstance(items, (list, set, tuple)):
            grouped = {}
            for path in items:
                parent, member = parent_path_and_member(path)
                grouped.setdefault(parent, set()).add(member)
            result[key] = grouped

    if ignore_order:
        for src, dst in (
            ("iterable_item_added", "iterable_items_added_at_indexes"),
            ("iterable_item_removed", "iterable_items_removed_at_indexes"),
        ):
            items = result.pop(src, None)
            if not items:
                continue
            bucket = result.setdefault(dst, {})
            for path, value in items.items():
                parent, index = parent_path_and_member(path)
                bucket.setdefault(parent, {})[index] = value
        # repetition_change is informational for reports; Delta apply uses index maps.
        result.pop("repetition_change", None)

    type_changes = result.get("type_changes")
    if isinstance(type_changes, Mapping) and not always_include_values:
        for path, value in list(type_changes.items()):
            if not isinstance(value, Mapping):
                continue
            value = dict(value)
            old_type, new_type = value.get("old_type"), value.get("new_type")
            if "old_value" in value and "new_value" in value and callable(new_type):
                try:
                    if new_type(value["old_value"]) == value["new_value"]:
                        value.pop("old_value", None)
                        value.pop("new_value", None)
                except Exception:
                    pass
            type_changes[path] = value

    if directed and not always_include_values:
        for _report_key, report_value in result.items():
            if isinstance(report_value, Mapping):
                for path, value in list(report_value.items()):
                    if isinstance(value, Mapping) and "old_value" in value:
                        value = dict(value)
                        del value["old_value"]
                        report_value[path] = value

    # drop empty
    return {k: v for k, v in result.items() if v}


class Delta:
    def __init__(
        self,
        diff=None,
        *,
        delta_diff=None,
        mutate=False,
        raise_errors=False,
        log_errors=True,
        bidirectional=False,
        always_include_values=False,
        force=False,
        fill=_NOT_FOUND,
        verify_symmetry=None,
        # intentionally unsupported in this phase:
        delta_path=None,
        delta_file=None,
        flat_dict_list=None,
        flat_rows_list=None,
        deserializer=None,
        serializer=None,
        safe_to_import=None,
        iterable_compare_func_was_used=None,
    ):
        if any(x is not None for x in (delta_path, delta_file, flat_dict_list, flat_rows_list)):
            raise NotImplementedError(
                "delta_path/delta_file/flat_dict_list/flat_rows_list are not supported yet"
            )

        if verify_symmetry is not None:
            logger.warning(
                "DeepDiff Deprecation: use bidirectional instead of verify_symmetry parameter."
            )
            bidirectional = verify_symmetry

        self.bidirectional = bidirectional
        self.always_include_values = True if bidirectional else always_include_values
        self.mutate = mutate
        self.raise_errors = raise_errors
        self.log_errors = log_errors
        self.force = force
        self.fill = fill
        self.deserializer = deserializer
        self.serializer = serializer
        self._reversed_diff = None
        self.post_process_paths_to_convert = {}
        self.get_nested_obj = get_nested_obj_and_force if force else get_nested_obj

        if diff is not None:
            to_delta = getattr(diff, "_to_delta_dict", None)
            if callable(to_delta):
                self.diff = to_delta(
                    directed=not bidirectional,
                    always_include_values=self.always_include_values,
                )
            elif isinstance(diff, Mapping):
                # Mapping payloads ignore deserializer (DeepDiff behavior).
                self.diff = dict(diff)
            elif isinstance(diff, (str, bytes)):
                self.diff = dict(_deserialize_diff(diff, deserializer, safe_to_import))
            else:
                raise TypeError(f"unsupported diff type: {type(diff).__name__}")
        elif delta_diff is not None:
            self.diff = dict(delta_diff)
        else:
            raise ValueError(_DELTA_AT_LEAST_ONE)

        self._numpy_paths = self.diff.get("_numpy_paths", False)
        self._iterable_compare_func_was_used = self.diff.get(
            "_iterable_compare_func_was_used", iterable_compare_func_was_used
        )

    def __repr__(self):
        text = str(self.diff)
        if len(text) > 100:
            text = text[:97] + "..."
        return f"<Delta: {text}>"

    def reset(self):
        self.post_process_paths_to_convert = {}

    def to_dict(self):
        return dict(self.diff)

    def dumps(self):
        """Serialize this delta with the configured `serializer` (if any)."""
        if self.serializer is None:
            raise NotImplementedError(
                "dumps() requires serializer=... at Delta creation "
                "(pickle default is not bundled; pass json.dumps or another callable)"
            )
        return self.serializer(self.diff)

    def dump(self, file):
        """Write a serialized delta to a file object."""
        payload = self.dumps()
        if isinstance(payload, str):
            file.write(payload)
        else:
            file.write(payload)

    def _raise_or_log(self, msg, level="error"):
        if self.log_errors:
            getattr(logger, level)(msg)
        if self.raise_errors:
            raise DeltaError(msg)

    def __add__(self, other):
        if isinstance(other, Number) and self._numpy_paths:
            raise DeltaNumpyOperatorOverrideError(_NUMPY_ADD)
        self.root = other if self.mutate else deepcopy(other)
        self.reset()
        self._do_values_changed()
        self._do_set_item_added()
        self._do_set_item_removed()
        self._do_type_changes()
        self._do_iterable_item_removed()
        self._do_iterable_item_added()
        self._do_ignore_order()
        self._do_dictionary_item_added()
        self._do_dictionary_item_removed()
        self._do_attribute_added()
        self._do_attribute_removed()
        self._do_post_process()
        result = self.root
        del self.root
        self.reset()
        return result

    __radd__ = __add__

    def __rsub__(self, other):
        if not self.bidirectional:
            raise ValueError("Please recreate the delta with bidirectional=True")
        if self._reversed_diff is None:
            self._reversed_diff = self._get_reverse_diff()
        self.diff, self._reversed_diff = self._reversed_diff, self.diff
        try:
            return self.__add__(other)
        finally:
            self.diff, self._reversed_diff = self._reversed_diff, self.diff

    def _get_reverse_diff(self):
        """Best-effort reverse for values/type/dict/iterable/set item maps."""
        src = self.diff
        out = {}
        if "values_changed" in src:
            out["values_changed"] = {
                path: {
                    "new_value": value.get("old_value", _NOT_FOUND),
                    "old_value": value.get("new_value", _NOT_FOUND),
                    **({"new_path": value["new_path"]} if "new_path" in value else {}),
                }
                for path, value in src["values_changed"].items()
            }
        if "type_changes" in src:
            out["type_changes"] = {
                path: {
                    "old_type": value.get("new_type"),
                    "new_type": value.get("old_type"),
                    **(
                        {"old_value": value["new_value"], "new_value": value["old_value"]}
                        if "old_value" in value and "new_value" in value
                        else {}
                    ),
                }
                for path, value in src["type_changes"].items()
            }
        swaps = (
            ("dictionary_item_added", "dictionary_item_removed"),
            ("dictionary_item_removed", "dictionary_item_added"),
            ("iterable_item_added", "iterable_item_removed"),
            ("iterable_item_removed", "iterable_item_added"),
            ("attribute_added", "attribute_removed"),
            ("attribute_removed", "attribute_added"),
            ("set_item_added", "set_item_removed"),
            ("set_item_removed", "set_item_added"),
            ("iterable_items_added_at_indexes", "iterable_items_removed_at_indexes"),
            ("iterable_items_removed_at_indexes", "iterable_items_added_at_indexes"),
        )
        for a, b in swaps:
            if a in src:
                out[b] = deepcopy(src[a])
        return out

    def _do_verify_changes(self, path, expected_old_value, current_old_value):
        if self.bidirectional and expected_old_value != current_old_value:
            self._raise_or_log(
                _VERIFICATION.format(path, expected_old_value, current_old_value, _VERIFY_BI)
            )

    def _get_elem_and_compare_to_old_value(
        self,
        obj,
        path_for_err_reporting,
        expected_old_value,
        elem=None,
        action=None,
        forced_old_value=None,
        next_element=None,
    ):
        check_elem(elem)
        try:
            if action == GET:
                current_old_value = obj[elem]
            elif action == GETATTR:
                current_old_value = getattr(obj, elem)
            else:
                raise DeltaError(f"invalid action of {action} when calling get elem")
        except (KeyError, IndexError, AttributeError, TypeError) as exc:
            if self.force:
                if forced_old_value is None:
                    _forced = {} if next_element is None or isinstance(next_element, str) else []
                else:
                    _forced = forced_old_value
                if action == GET:
                    if isinstance(obj, list):
                        if isinstance(elem, int) and elem < len(obj):
                            obj[elem] = _forced
                        else:
                            obj.append(_forced)
                    else:
                        obj[elem] = _forced
                elif action == GETATTR:
                    setattr(obj, elem, _forced)
                return _forced
            current_old_value = _NOT_FOUND
            if self.bidirectional:
                self._raise_or_log(
                    _VERIFICATION.format(path_for_err_reporting, expected_old_value, current_old_value, exc)
                )
            else:
                self._raise_or_log(_UNABLE_PATH.format(path_for_err_reporting))
        return current_old_value

    def _simple_set_elem_value(self, obj, path_for_err_reporting, elem=None, value=None, action=None):
        try:
            if action == GET:
                try:
                    obj[elem] = value
                except IndexError:
                    if elem == len(obj):
                        obj.append(value)
                    elif self.fill is not _NOT_FOUND and elem is not None and elem > len(obj):
                        while len(obj) < elem:
                            obj.append(self.fill(obj, value, path_for_err_reporting) if callable(self.fill) else self.fill)
                        obj.append(value)
                    else:
                        self._raise_or_log(_ELEM_NOT_FOUND.format(elem, path_for_err_reporting))
            elif action == GETATTR:
                setattr(obj, elem, value)
            else:
                raise DeltaError(f"invalid action of {action} when calling set elem")
        except (KeyError, IndexError, AttributeError, TypeError) as exc:
            self._raise_or_log(f"Failed to set {path_for_err_reporting} due to {exc}")

    def _simple_delete_elem(self, obj, path_for_err_reporting, elem=None, action=None):
        try:
            if action == GET:
                del obj[elem]
            elif action == GETATTR:
                del obj.__dict__[elem]
            else:
                raise DeltaError(f"invalid action of {action} when calling delete elem")
        except (KeyError, IndexError, AttributeError) as exc:
            self._raise_or_log(f"Failed to set {path_for_err_reporting} due to {exc}")

    def _coerce_obj(self, parent, obj, path, parent_to_obj_elem, parent_to_obj_action, elements, to_type, from_type):
        self.post_process_paths_to_convert[elements[:-1]] = {
            "old_type": to_type,
            "new_type": from_type,
        }
        obj = to_type(obj)
        if parent is not None:
            self._simple_set_elem_value(
                obj=parent,
                path_for_err_reporting=path,
                elem=parent_to_obj_elem,
                value=obj,
                action=parent_to_obj_action,
            )
        return obj

    def _set_new_value(
        self, parent, parent_to_obj_elem, parent_to_obj_action, obj, elements, path, elem, action, new_value
    ):
        if isinstance(obj, tuple):
            if hasattr(obj, "_fields") and hasattr(obj, "_replace"):
                if action == GETATTR:
                    obj = obj._replace(**{elem: new_value})
                    if parent is not None:
                        self._simple_set_elem_value(
                            obj=parent,
                            path_for_err_reporting=path,
                            elem=parent_to_obj_elem,
                            value=obj,
                            action=parent_to_obj_action,
                        )
                return
            obj = self._coerce_obj(
                parent, obj, path, parent_to_obj_elem, parent_to_obj_action, elements, list, tuple
            )
        if elem != 0 and self.force and isinstance(obj, list) and len(obj) == 0:
            obj = {}
            self._simple_set_elem_value(
                obj=parent,
                path_for_err_reporting=path,
                elem=parent_to_obj_elem,
                value=obj,
                action=parent_to_obj_action,
            )
        self._simple_set_elem_value(
            obj=obj, path_for_err_reporting=path, elem=elem, value=new_value, action=action
        )

    def _del_elem(
        self, parent, parent_to_obj_elem, parent_to_obj_action, obj, elements, path, elem, action
    ):
        obj_is_new = False
        if isinstance(obj, tuple):
            self.post_process_paths_to_convert[elements[:-1]] = {
                "old_type": list,
                "new_type": tuple,
            }
            obj = list(obj)
            obj_is_new = True
        self._simple_delete_elem(obj=obj, path_for_err_reporting=path, elem=elem, action=action)
        if obj_is_new and parent is not None:
            self._simple_set_elem_value(
                obj=parent,
                path_for_err_reporting=path,
                elem=parent_to_obj_elem,
                value=obj,
                action=parent_to_obj_action,
            )

    def _get_elements_and_details(self, path):
        try:
            elements = path_to_elements(path)
            for elem, _ in elements:
                check_elem(elem)
            if len(elements) > 1:
                elements_subset = elements[:-2]
                next_element = elements[-2][0] if len(elements_subset) != len(elements) else None
                next2_element = elements[-1][0]
                parent = self.get_nested_obj(
                    obj=self, elements=elements_subset, next_element=next_element
                )
                parent_to_obj_elem, parent_to_obj_action = elements[-2]
                obj = self._get_elem_and_compare_to_old_value(
                    obj=parent,
                    path_for_err_reporting=path,
                    expected_old_value=None,
                    elem=parent_to_obj_elem,
                    action=parent_to_obj_action,
                    next_element=next2_element,
                )
            else:
                parent = parent_to_obj_elem = parent_to_obj_action = None
                obj = self
            elem, action = elements[-1]
        except Exception as exc:
            if isinstance(exc, ValueError) and str(exc) == "traversing dunder attributes is not allowed":
                raise
            self._raise_or_log(_UNABLE_GET.format(path, exc))
            return None
        if obj is _NOT_FOUND:
            return None
        return elements, parent, parent_to_obj_elem, parent_to_obj_action, obj, elem, action

    @staticmethod
    def _sort_key_for_item_added(path_and_value):
        return [i[0] for i in path_to_elements(path_and_value[0])]

    @staticmethod
    def _sort_comparison(left, right):
        left_path = [i[0] for i in path_to_elements(left[0], root_element=None)]
        right_path = [i[0] for i in path_to_elements(right[0], root_element=None)]
        try:
            return (left_path > right_path) - (left_path < right_path)
        except TypeError:
            left_path = [str(x) for x in left_path]
            right_path = [str(x) for x in right_path]
            return (left_path > right_path) - (left_path < right_path)

    def _do_item_added(self, items, sort=True, insert=False):
        if sort:
            try:
                items = sorted(items.items(), key=self._sort_key_for_item_added)
            except TypeError:
                items = sorted(items.items(), key=cmp_to_key(self._sort_comparison))
        else:
            items = items.items()
        for path, new_value in items:
            details = self._get_elements_and_details(path)
            if not details:
                continue
            elements, parent, parent_to_obj_elem, parent_to_obj_action, obj, elem, action = details
            if insert and isinstance(obj, list) and isinstance(elem, int) and elem < len(obj):
                obj.insert(elem, None)
            self._set_new_value(
                parent, parent_to_obj_elem, parent_to_obj_action, obj, elements, path, elem, action, new_value
            )

    def _do_item_removed(self, items):
        try:
            sorted_item = sorted(items.items(), key=self._sort_key_for_item_added, reverse=True)
        except TypeError:
            sorted_item = sorted(items.items(), key=cmp_to_key(self._sort_comparison), reverse=True)
        for path, expected_old_value in sorted_item:
            details = self._get_elements_and_details(path)
            if not details:
                continue
            elements, parent, parent_to_obj_elem, parent_to_obj_action, obj, elem, action = details
            current_old_value = self._get_elem_and_compare_to_old_value(
                obj=obj,
                path_for_err_reporting=path,
                expected_old_value=expected_old_value,
                elem=elem,
                action=action,
            )
            if current_old_value is _NOT_FOUND:
                continue
            self._del_elem(
                parent, parent_to_obj_elem, parent_to_obj_action, obj, elements, path, elem, action
            )
            self._do_verify_changes(path, expected_old_value, current_old_value)

    def _do_values_or_type_changed(self, changes, is_type_change=False, verify_changes=True):
        compare_func_was_used = self.diff.get("_iterable_compare_func_was_used", False)
        for path, value in changes.items():
            apply_path = (
                value["new_path"]
                if (compare_func_was_used and isinstance(value, Mapping) and value.get("new_path"))
                else path
            )
            details = self._get_elements_and_details(apply_path)
            if not details:
                continue
            elements, parent, parent_to_obj_elem, parent_to_obj_action, obj, elem, action = details
            expected_old_value = value.get("old_value", _NOT_FOUND) if isinstance(value, Mapping) else _NOT_FOUND
            current_old_value = self._get_elem_and_compare_to_old_value(
                obj=obj,
                path_for_err_reporting=path,
                expected_old_value=expected_old_value,
                elem=elem,
                action=action,
            )
            if current_old_value is _NOT_FOUND:
                continue
            if is_type_change and isinstance(value, Mapping) and "new_value" not in value:
                try:
                    new_type = value["new_type"]
                    new_value = new_type(current_old_value)
                except Exception as exc:
                    self._raise_or_log(_TYPE_CHANGE_FAIL.format(obj[elem], value.get("new_type", "unknown"), exc))
                    continue
            else:
                new_value = value["new_value"] if isinstance(value, Mapping) else value
            self._set_new_value(
                parent, parent_to_obj_elem, parent_to_obj_action, obj, elements, path, elem, action, new_value
            )
            if verify_changes:
                self._do_verify_changes(path, expected_old_value, current_old_value)

    def _do_values_changed(self):
        values_changed = self.diff.get("values_changed")
        if values_changed:
            self._do_values_or_type_changed(values_changed)

    def _do_type_changes(self):
        type_changes = self.diff.get("type_changes")
        if type_changes:
            self._do_values_or_type_changed(type_changes, is_type_change=True)

    def _do_post_process(self):
        if self.post_process_paths_to_convert:
            self._do_values_or_type_changed(
                self.post_process_paths_to_convert, is_type_change=True, verify_changes=False
            )

    def _do_dictionary_item_added(self):
        items = self.diff.get("dictionary_item_added")
        if items:
            self._do_item_added(items, sort=False)

    def _do_dictionary_item_removed(self):
        items = self.diff.get("dictionary_item_removed")
        if items:
            self._do_item_removed(items)

    def _do_attribute_added(self):
        items = self.diff.get("attribute_added")
        if items:
            self._do_item_added(items)

    def _do_attribute_removed(self):
        items = self.diff.get("attribute_removed")
        if items:
            self._do_item_removed(items)

    def _do_iterable_item_added(self):
        items = dict(self.diff.get("iterable_item_added", {}) or {})
        moved = self.diff.get("iterable_item_moved")
        if moved:
            items.update({v["new_path"]: None for v in moved.values()})
        if items:
            self._do_item_added(items, insert=True)
        if moved:
            self._do_item_added({v["new_path"]: v["value"] for v in moved.values()}, insert=False)

    def _do_iterable_item_removed(self):
        items = dict(self.diff.get("iterable_item_removed", {}) or {})
        moved = self.diff.get("iterable_item_moved")
        if moved:
            items.update({k: v["value"] for k, v in moved.items()})
        if items:
            self._do_item_removed(items)

    def _do_set_item_added(self):
        items = self.diff.get("set_item_added")
        if items:
            self._do_set_or_frozenset_item(items, "union")

    def _do_set_item_removed(self):
        items = self.diff.get("set_item_removed")
        if items:
            self._do_set_or_frozenset_item(items, "difference")

    def _do_set_or_frozenset_item(self, items, func):
        for path, value in items.items():
            details = self._get_elements_and_details(path)
            if not details:
                continue
            elements, parent, parent_to_obj_elem, parent_to_obj_action, obj, elem, action = details
            obj = self._get_elem_and_compare_to_old_value(
                obj,
                path_for_err_reporting=path,
                expected_old_value=None,
                elem=elem,
                action=action,
                forced_old_value=set(),
            )
            new_value = getattr(obj, func)(value)
            set_parent = self.get_nested_obj(obj=self, elements=elements[:-1])
            replace = getattr(set_parent, "_replace", None)
            if hasattr(set_parent, "_fields") and callable(replace):
                new_parent = replace(**{elem: new_value})
                if parent is None:
                    self.root = new_parent
                else:
                    self._simple_set_elem_value(
                        parent,
                        path_for_err_reporting=path,
                        elem=parent_to_obj_elem,
                        value=new_parent,
                        action=parent_to_obj_action,
                    )
            else:
                self._simple_set_elem_value(
                    set_parent, path_for_err_reporting=path, elem=elem, value=new_value, action=action
                )

    def _do_ignore_order(self):
        added = self.diff.get("iterable_items_added_at_indexes")
        removed = self.diff.get("iterable_items_removed_at_indexes")
        if not added and not removed:
            return
        # Rebuild each path: keep items not removed, then place added at indexes.
        paths = set(added or {}) | set(removed or {})
        for path in paths:
            details = self._get_elements_and_details(path)
            if not details:
                continue
            _elements, parent, parent_to_obj_elem, parent_to_obj_action, obj, elem, action = details
            seq = self._get_elem_and_compare_to_old_value(
                obj,
                path_for_err_reporting=path,
                expected_old_value=None,
                elem=elem,
                action=action,
                forced_old_value=[],
            )
            if not isinstance(seq, list):
                seq = list(seq)
            remove_map = dict((removed or {}).get(path, {}) or {})
            add_map = dict((added or {}).get(path, {}) or {})
            fixed = set(add_map.values())  # noqa: F841 — DeepDiff uses for skip; keep rebuild simple
            kept = []
            for idx, item in enumerate(seq):
                if idx in remove_map and remove_map[idx] == item:
                    continue
                if idx in remove_map:
                    # value mismatch — still drop by index when not bidirectional-strict
                    continue
                kept.append(item)
            # Place added items at their indexes (DeepDiff rebuild is more involved;
            # this matches common list rewrite cases).
            if add_map:
                new_seq = list(kept)
                for index in sorted(add_map):
                    value = add_map[index]
                    if index <= len(new_seq):
                        new_seq.insert(index, value)
                    else:
                        new_seq.extend([None] * (index - len(new_seq)))
                        new_seq.append(value)
                kept = new_seq
            self._simple_set_elem_value(
                obj, path_for_err_reporting=path, elem=elem, value=kept, action=action
            )
            if parent is not None:
                self._simple_set_elem_value(
                    parent,
                    path_for_err_reporting=path,
                    elem=parent_to_obj_elem,
                    value=obj if action != GETATTR else kept,
                    action=parent_to_obj_action,
                )
