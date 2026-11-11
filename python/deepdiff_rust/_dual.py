"""Native dual walk for custom_operators and iterable_compare_func."""

from collections.abc import Mapping, Sequence

from ._callbacks import Level

_SENTINEL = object()


def _is_seq(x):
    return isinstance(x, Sequence) and not isinstance(x, (str, bytes, bytearray))


def _remap(path, prefix):
    if path == "root":
        return prefix
    return prefix + path[4:]


def _merge_native(into, native_dict, prefix):
    for category, findings in native_dict.items():
        if category == "deep_distance":
            continue
        bucket = into.setdefault(category, {})
        if isinstance(findings, dict):
            for path, payload in findings.items():
                bucket[_remap(path, prefix)] = payload
        else:
            bucket.update(findings)


def _matching_pairs(t1, t2, level, compare_func):
    if compare_func is None:
        from itertools import zip_longest
        return [
            ((i, i), (x, y))
            for i, (x, y) in enumerate(zip_longest(t1, t2, fillvalue=_SENTINEL))
        ]
    matches = []
    y_matched = set()
    for i, x in enumerate(t1):
        found = False
        for j, y in enumerate(t2):
            if j in y_matched:
                continue
            try:
                ok = compare_func(x, y, level)
            except Exception:
                ok = False
            if ok:
                y_matched.add(j)
                matches.append(((i, j), (x, y)))
                found = True
                break
        if not found:
            matches.append(((i, -1), (x, _SENTINEL)))
    for j, y in enumerate(t2):
        if j not in y_matched:
            matches.append(((-1, j), (_SENTINEL, y)))
    return matches


def walk_diff(diff_instance, t1, t2, path, native_factory):
    level = Level(t1, t2, path)
    for operator in diff_instance.custom_operators:
        if operator.match(level) and operator.give_up_diffing(level, diff_instance):
            return
    if _skip_obj(diff_instance, t1, t2, path):
        return
    if t1 is t2:
        return
    if isinstance(t1, Mapping) and isinstance(t2, Mapping):
        _walk_mapping(diff_instance, t1, t2, path, native_factory)
        return
    if _is_seq(t1) and _is_seq(t2):
        _walk_seq(diff_instance, t1, t2, path, native_factory)
        return
    _merge_native(diff_instance._walk_report, native_factory(t1, t2), path)


def _skip_obj(diff_instance, t1, t2, path):
    ex = diff_instance.exclude_obj_callback
    if ex and (ex(t1, path) or ex(t2, path)):
        return True
    exs = diff_instance.exclude_obj_callback_strict
    if exs and exs(t1, path) and exs(t2, path):
        return True
    inc = diff_instance.include_obj_callback
    if inc and path != "root" and not (inc(t1, path) or inc(t2, path)):
        return True
    incs = diff_instance.include_obj_callback_strict
    if incs and path != "root" and not (incs(t1, path) and incs(t2, path)):
        return True
    return False


def _walk_mapping(diff_instance, t1, t2, path, native_factory):
    for key in set(t1) | set(t2):
        child = f"{path}[{key!r}]"
        if key in t1 and key in t2:
            walk_diff(diff_instance, t1[key], t2[key], child, native_factory)
        elif key in t1:
            diff_instance._walk_report.setdefault("dictionary_item_removed", {})[child] = t1[key]
        else:
            diff_instance._walk_report.setdefault("dictionary_item_added", {})[child] = t2[key]


def _walk_seq(diff_instance, t1, t2, path, native_factory):
    level = Level(t1, t2, path)
    pairs = _matching_pairs(t1, t2, level, diff_instance.iterable_compare_func)
    for (i, j), (x, y) in pairs:
        if x is _SENTINEL:
            child = f"{path}[{j}]"
            diff_instance._walk_report.setdefault("iterable_item_added", {})[child] = y
        elif y is _SENTINEL:
            child = f"{path}[{i}]"
            diff_instance._walk_report.setdefault("iterable_item_removed", {})[child] = x
        else:
            moved = i != j and diff_instance.iterable_compare_func
            child = f"{path}[{j if moved else i}]"
            if moved and diff_instance.verbose_level > 1:
                bucket = diff_instance._walk_report.setdefault("iterable_item_moved", {})
                bucket[f"{path}[{i}]"] = {"new_path": f"{path}[{j}]", "value": y}
            walk_diff(diff_instance, x, y, child, native_factory)


def run_dual(diff_instance, t1, t2, native_factory):
    diff_instance._walk_report = {}
    walk_diff(diff_instance, t1, t2, "root", native_factory)
    return diff_instance._walk_report
