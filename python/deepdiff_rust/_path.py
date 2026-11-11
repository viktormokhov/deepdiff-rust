"""Path parsing and `extract` — DeepDiff-compatible `root[...]` / attribute paths.

Logic adapted from DeepDiff's `path` module (MIT) for the subset Delta needs.
"""

from __future__ import annotations

from ast import literal_eval
from functools import lru_cache

GETATTR = "GETATTR"
GET = "GET"
DEFAULT_FIRST_ELEMENT = ("root", GETATTR)


def check_elem(elem) -> None:
    if isinstance(elem, str) and elem.startswith("__") and elem.endswith("__"):
        raise ValueError("traversing dunder attributes is not allowed")


def _add_to_elements(elements, elem, inside) -> None:
    if not elem or elem.startswith("__"):
        return
    remove_quotes = False
    if "\U0001d186" in elem or "\\" in elem:
        remove_quotes = True
    else:
        try:
            elem = literal_eval(elem)
            remove_quotes = False
        except (ValueError, SyntaxError):
            remove_quotes = True
    if remove_quotes and elem[0] == elem[-1] and elem[0] in {'"', "'"}:
        elem = elem[1:-1]
    action = GETATTR if inside == "." else GET
    elements.append((elem, action))


@lru_cache(maxsize=1024 * 128)
def path_to_elements(path, root_element=DEFAULT_FIRST_ELEMENT):
    if isinstance(path, (tuple, list)):
        return path
    elements = []
    if root_element:
        elements.append(root_element)
    elem = ""
    inside = False
    prev_char = None
    path = path[4:]  # strip leading "root"
    brackets = []
    inside_quotes = False
    quote_used = ""
    for char in path:
        if prev_char == "\U0001d186":
            elem += char
        elif char in {'"', "'"}:
            elem += char
            if not (inside_quotes and quote_used != char):
                inside_quotes = not inside_quotes
                if inside_quotes:
                    quote_used = char
                else:
                    _add_to_elements(elements, elem, inside)
                    elem = ""
                    quote_used = ""
        elif inside_quotes:
            elem += char
        elif char == "[":
            if inside == ".":
                _add_to_elements(elements, elem, inside)
                inside = "["
                elem = ""
            elif inside == "[":
                elem += char
            else:
                inside = "["
                brackets.append("[")
                elem = ""
        elif char == ".":
            if inside == "[":
                elem += char
            elif inside == ".":
                _add_to_elements(elements, elem, inside)
                elem = ""
            else:
                inside = "."
                elem = ""
        elif char == "]":
            if brackets and brackets[-1] == "[":
                brackets.pop()
            if brackets:
                elem += char
            else:
                _add_to_elements(elements, elem, inside)
                elem = ""
                inside = False
        else:
            elem += char
        prev_char = char
    if elem:
        _add_to_elements(elements, elem, inside)
    return tuple(elements)


def get_nested_obj(obj, elements, next_element=None):
    for elem, action in elements:
        check_elem(elem)
        if action == GET:
            obj = obj[elem]
        elif action == GETATTR:
            obj = getattr(obj, elem)
    return obj


def _guess_type(elements, index, next_element):
    if index < len(elements) - 1:
        return {}
    if isinstance(next_element, int):
        return []
    return {}


def get_nested_obj_and_force(obj, elements, next_element=None):
    prev_elem = None
    prev_action = None
    prev_obj = obj
    for index, (elem, action) in enumerate(elements):
        check_elem(elem)
        _prev_obj = obj
        if action == GET:
            try:
                obj = obj[elem]
                prev_obj = _prev_obj
            except KeyError:
                obj[elem] = _guess_type(elements, index, next_element)
                obj = obj[elem]
                prev_obj = _prev_obj
            except IndexError:
                if isinstance(obj, list) and isinstance(elem, int) and elem >= len(obj):
                    obj.extend([None] * (elem - len(obj)))
                    obj.append(_guess_type(elements, index, next_element))
                    obj = obj[-1]
                    prev_obj = _prev_obj
                elif isinstance(obj, list) and len(obj) == 0 and prev_elem is not None:
                    obj = {elem: _guess_type(elements, index, next_element)}
                    if prev_action == GET:
                        prev_obj[prev_elem] = obj
                    else:
                        setattr(prev_obj, str(prev_elem), obj)
                    obj = obj[elem]
        elif action == GETATTR:
            obj = getattr(obj, elem)
            prev_obj = _prev_obj
        prev_elem = elem
        prev_action = action
    return obj


def extract(obj, path):
    """Return the value at a DeepDiff-style path (`root[...]`)."""
    elements = path_to_elements(path, root_element=None)
    return get_nested_obj(obj, elements)


def parent_path_and_member(path: str):
    """Split ``root['s'][3]`` into parent path ``root['s']`` and member ``3``."""
    elements = path_to_elements(path, root_element=DEFAULT_FIRST_ELEMENT)
    if len(elements) < 2:
        raise ValueError(f"path too short to split: {path!r}")
    member, _ = elements[-1]
    parent_elems = elements[:-1]
    # rebuild a minimal parent path string from elements (best-effort)
    parts = ["root"]
    for elem, action in parent_elems[1:]:
        if action == GETATTR:
            parts.append(f".{elem}")
        else:
            parts.append(f"[{elem!r}]" if isinstance(elem, str) else f"[{elem}]")
    return "".join(parts), member
