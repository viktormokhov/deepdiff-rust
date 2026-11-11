"""DeepDiff callback helpers: Level, activity, object-callback skip."""

from collections.abc import Mapping

from ._paths import _elements


class Level:
    """Minimal DeepDiff-compatible level for operators and iterable_compare_func."""

    __slots__ = ("t1", "t2", "_path")

    def __init__(self, t1, t2, path="root"):
        self.t1 = t1
        self.t2 = t2
        self._path = path

    def path(self):
        return self._path


def callbacks_active(
    *,
    custom_operators=None,
    exclude_obj_callback=None,
    exclude_obj_callback_strict=None,
    include_obj_callback=None,
    include_obj_callback_strict=None,
    iterable_compare_func=None,
):
    return any(
        (
            custom_operators,
            exclude_obj_callback,
            exclude_obj_callback_strict,
            include_obj_callback,
            include_obj_callback_strict,
            iterable_compare_func,
        )
    )


def _child(obj, seg):
    if isinstance(obj, Mapping):
        return obj[seg]
    if isinstance(seg, int) and isinstance(obj, (list, tuple)):
        return obj[seg]
    return getattr(obj, seg)


def resolve(root, path):
    if path == "root":
        return root
    cur = root
    for seg in _elements(path):
        cur = _child(cur, seg)
    return cur


def compose_skip(
    base_skip,
    t1,
    t2,
    *,
    exclude_obj_callback=None,
    exclude_obj_callback_strict=None,
    include_obj_callback=None,
    include_obj_callback_strict=None,
):
    """Retain-filter skip plus DeepDiff object-callback branch of `_skip_this`."""
    if not any(
        (
            exclude_obj_callback,
            exclude_obj_callback_strict,
            include_obj_callback,
            include_obj_callback_strict,
        )
    ):
        return base_skip

    def skip_obj(path):
        try:
            o1, o2 = resolve(t1, path), resolve(t2, path)
        except (KeyError, IndexError, AttributeError, TypeError):
            o1 = o2 = None
        if exclude_obj_callback and (
            exclude_obj_callback(o1, path) or exclude_obj_callback(o2, path)
        ):
            return True
        if exclude_obj_callback_strict and (
            exclude_obj_callback_strict(o1, path)
            and exclude_obj_callback_strict(o2, path)
        ):
            return True
        if include_obj_callback and path != "root":
            return not (
                include_obj_callback(o1, path) or include_obj_callback(o2, path)
            )
        if include_obj_callback_strict and path != "root":
            return not (
                include_obj_callback_strict(o1, path)
                and include_obj_callback_strict(o2, path)
            )
        return False

    def skip(prefixes, typed):
        if base_skip and base_skip(prefixes, typed):
            return True
        return any(skip_obj(path) for path in prefixes)

    return skip

def _deepdiff_bridge(t1, t2, **kwargs):
    """Parity bridge for callbacks that must run during the walk."""
    try:
        from deepdiff import DeepDiff as RealDeepDiff
    except ImportError as exc:
        raise ImportError(
            "iterable_compare_func and custom_operators require the deepdiff "
            "package installed until the native dual-walk hooks land"
        ) from exc
    return RealDeepDiff(t1, t2, **kwargs)
