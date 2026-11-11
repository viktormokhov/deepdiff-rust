"""pretty() and view='tree' DiffLevel."""


class DiffLevel:
    __slots__ = ("t1", "t2", "report_type", "_path", "additional")

    def __init__(self, path, t1, t2, report_type):
        self._path = path
        self.t1 = t1
        self.t2 = t2
        self.report_type = report_type
        self.additional = {}

    def path(self, root="root", **_kwargs):
        if root == "root":
            return self._path
        if self._path == "root":
            return root
        return root + self._path[4:]

    def __repr__(self):
        return f"<{self._path} t1:{self.t1!r}, t2:{self.t2!r}>"


_PRETTY = {
    "type_changes": (
        "Type of {diff_path} changed from {type_t1} to {type_t2} "
        "and value changed from {val_t1} to {val_t2}."
    ),
    "values_changed": "Value of {diff_path} changed from {val_t1} to {val_t2}.",
    "dictionary_item_added": "Item {diff_path} added to dictionary.",
    "dictionary_item_removed": "Item {diff_path} removed from dictionary.",
    "iterable_item_added": "Item {diff_path} added to iterable.",
    "iterable_item_removed": "Item {diff_path} removed from iterable.",
    "attribute_added": "Attribute {diff_path} added.",
    "attribute_removed": "Attribute {diff_path} removed.",
    "set_item_added": "Item root[{val_t2}] added to set.",
    "set_item_removed": "Item root[{val_t1}] removed from set.",
    "repetition_change": "Repetition change for item {diff_path}.",
    "iterable_item_moved": "Item {diff_path} moved to {val_t2}.",
}

_PRETTY_V2 = {
    **_PRETTY,
    "dictionary_item_added": "Item {diff_path} ({val_t2}) added to dictionary.",
    "dictionary_item_removed": "Item {diff_path} ({val_t1}) removed from dictionary.",
    "iterable_item_added": "Item {diff_path} ({val_t2}) added to iterable.",
    "iterable_item_removed": "Item {diff_path} ({val_t1}) removed from iterable.",
    "attribute_added": "Attribute {diff_path} ({val_t2}) added.",
    "attribute_removed": "Attribute {diff_path} ({val_t1}) removed.",
}


def _fmt_val(value):
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)


def _iter_findings(findings):
    if isinstance(findings, dict):
        yield from findings.items()
    else:
        for path in findings:
            yield path, None


def _level_from_finding(report_type, path, payload):
    if report_type == "values_changed" and isinstance(payload, dict):
        return DiffLevel(path, payload.get("old_value"), payload.get("new_value"), report_type)
    if report_type == "type_changes" and isinstance(payload, dict):
        return DiffLevel(path, payload.get("old_value"), payload.get("new_value"), report_type)
    if report_type == "iterable_item_moved" and isinstance(payload, dict):
        return DiffLevel(path, payload.get("value"), payload.get("new_path"), report_type)
    if report_type == "repetition_change" and isinstance(payload, dict):
        return DiffLevel(path, payload.get("value"), payload.get("value"), report_type)
    if report_type.endswith("_added"):
        return DiffLevel(path, None, payload, report_type)
    if report_type.endswith("_removed"):
        return DiffLevel(path, payload, None, report_type)
    return DiffLevel(path, payload, payload, report_type)


def build_tree(report):
    tree = {}
    for report_type, findings in report.items():
        if report_type == "deep_distance":
            continue
        levels = [
            _level_from_finding(report_type, path, payload)
            for path, payload in _iter_findings(findings)
        ]
        if levels:
            tree[report_type] = levels
    return tree


def tree_as_result(tree):
    return {key: list(levels) for key, levels in tree.items()}


def pretty_from_tree(tree, verbose_level=1, prefix=None):
    forms = _PRETTY_V2 if verbose_level == 2 else _PRETTY
    if prefix is None:
        prefix = ""
    lines = []
    for report_type in sorted(tree):
        for level in tree[report_type]:
            template = forms.get(level.report_type, "")
            if not template:
                continue
            line = template.format(
                diff_path=level.path(),
                type_t1=type(level.t1).__name__,
                type_t2=type(level.t2).__name__,
                val_t1=_fmt_val(level.t1),
                val_t2=_fmt_val(level.t2),
            )
            if callable(prefix):
                lines.append(f"{prefix(diff=level)}{line}")
            else:
                lines.append(f"{prefix}{line}")
    return "\n".join(lines)
