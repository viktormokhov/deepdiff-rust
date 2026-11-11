"""DeepDiff callback helpers: Level and active-callback detection."""


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
