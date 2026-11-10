"""Path filters: deepdiff 9.1.0's `_skip_this` over rendered path strings."""

import ast
import re
from functools import cache

_WILDCARD_RE = re.compile(r"\[\*\*?\]|\.\*\*?(?=[.\[]|$)")
_ONE, _ANY = object(), object()


def _element(text, literal):
    if text in ("*", "**"):
        return _ONE if text == "*" else _ANY
    if not literal:
        return text
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text


@cache
def _elements(path):
    """`root['a'][0].b` -> ('a', 0, 'b'); `*`/`**` become wildcard markers."""
    out, i, n = [], 4, len(path)
    while i < n:
        j = i + 1
        if path[i] == ".":
            while j < n and path[j] not in ".[":
                j += 1
            out.append(_element(path[i + 1 : j], literal=False))
            i = j
            continue
        quote = None
        while j < n and (quote or path[j] != "]"):
            if quote and path[j] == "\\":
                j += 1
            elif path[j] == quote:
                quote = None
            elif not quote and path[j] in "'\"":
                quote = path[j]
            j += 1
        out.append(_element(path[i + 1 : j], literal=True))
        i = j + 1
    return tuple(out)


def _matches(pattern, target, prefix):
    """`pattern` matches `target`, or (`prefix`) some prefix of it."""

    @cache
    def go(p, t):
        if p == len(pattern):
            return prefix or t == len(target)
        if pattern[p] is _ANY:
            return any(go(p + 1, k) for k in range(t, len(target) + 1))
        if t == len(target):
            return False
        return (pattern[p] is _ONE or pattern[p] == target[t]) and go(p + 1, t + 1)

    return go(0, 0)


def _could_reach(pattern, target):
    """`target` is an ancestor of some path `pattern` matches."""

    @cache
    def go(p, t):
        if t == len(target):
            return p < len(pattern)
        if p == len(pattern):
            return False
        if pattern[p] is _ANY:
            return go(p + 1, t) or go(p, t + 1)
        return (pattern[p] is _ONE or pattern[p] == target[t]) and go(p + 1, t + 1)

    return go(0, 0)


def _root_paths(paths):
    """deepdiff's `add_root_to_paths`: a bare key also means `root[key]`."""
    result = set()
    for path in paths:
        if path.startswith("root"):
            result.add(path)
        elif path.isdigit():
            result |= {f"root['{path}']", f"root[{path}]"}
        elif path[0].isdigit():
            result.add(f"root['{path}']")
        else:
            result |= {f"root.{path}", f"root['{path}']"}
    return result


def _split(paths):
    """(exact paths, glob patterns as element tuples), as deepdiff separates them."""
    if not paths:
        return set(), []
    paths = {paths} if isinstance(paths, str) else set(paths)
    globs = []
    for path in paths:
        if _WILDCARD_RE.search(path):
            if not path.startswith("root"):
                raise ValueError(f"Wildcard paths must start with 'root'. Got: {path}")
            globs.append(_elements(path))
    exact = {path for path in paths if not _WILDCARD_RE.search(path)}
    return _root_paths(exact), globs


def _regexes(items):
    if not items:
        return []
    items = [items] if isinstance(items, (str, re.Pattern)) else list(items)
    return [item if isinstance(item, re.Pattern) else re.compile(item) for item in items]


def skip_filter(exclude_paths, include_paths, exclude_regex_paths, exclude_types):
    """`skip(prefixes, typed)` for a finding: `prefixes` are its path's rendered
    prefixes from `root`, `typed[k]` whether `prefixes[k]` holds an
    `exclude_types` instance. `None` when nothing filters."""
    ex_exact, ex_globs = _split(exclude_paths)
    in_exact, in_globs = _split(include_paths)
    regexes = _regexes(exclude_regex_paths)
    if not (ex_exact or ex_globs or in_exact or in_globs or regexes or exclude_types):
        return None

    def included(path):
        return path in in_exact or any(p in path or path in p for p in in_exact)

    @cache
    def skip_level(path, typed):
        if path in ex_exact or any(_matches(g, _elements(path), False) for g in ex_globs):
            return True
        if (in_exact or in_globs) and path != "root":
            if included(path):
                return False
            target = _elements(path)
            return not any(_matches(g, target, False) or _could_reach(g, target) for g in in_globs)
        if any(regex.search(path) for regex in regexes):
            return True
        return typed

    def skip_report(path):
        # `_skip_report_for_include_glob`: a glob ancestor is walked, not reported.
        if not in_globs or path in in_exact or any(p in path for p in in_exact):
            return False
        return not any(_matches(g, _elements(path), True) for g in in_globs)

    def skip(prefixes, typed):
        return any(map(skip_level, prefixes, typed)) or skip_report(prefixes[-1])

    return skip
