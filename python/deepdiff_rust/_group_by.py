"""group_by: regroup a list of dicts before the diff."""

from collections.abc import Iterable, Mapping
from copy import deepcopy


def _key(row, group_by):
    return group_by(row) if callable(group_by) else row.pop(group_by)


def _add(result, key, row, sort_key):
    if sort_key is None:
        result[key] = row
    elif row not in result.setdefault(key, []):
        result[key].append(row)


def _group(item, group_by, sort_key):
    level1, level2 = group_by, None
    if isinstance(group_by, (list, tuple)):
        level1, level2 = group_by[0], group_by[1] if len(group_by) > 1 else None
    if not isinstance(item, Iterable) or isinstance(item, Mapping):
        raise ValueError(f"Unable to group by {group_by}")
    result = {}
    for row in deepcopy(item):
        if not isinstance(row, Mapping):
            raise ValueError(f"Unable to group by {level1}: {row!r} is not a dictionary.")
        key1 = _key(row, level1)
        if level2:
            _add(result.setdefault(key1, {}), _key(row, level2), row, sort_key)
        else:
            _add(result, key1, row, sort_key)
    if sort_key is not None:
        groups = [g for sub in result.values() for g in sub.values()] if level2 else result.values()
        for rows in groups:
            rows.sort(key=sort_key)
    return result


def group_pair(t1, t2, group_by, group_by_sort_key):
    if not group_by:
        return t1, t2
    sort_key = group_by_sort_key
    if sort_key is not None and not callable(sort_key):
        name = sort_key

        def sort_key(row):
            return row[name]

    try:
        return _group(t1, group_by, sort_key), _group(t2, group_by, sort_key)
    except (KeyError, ValueError):
        return t1, t2
