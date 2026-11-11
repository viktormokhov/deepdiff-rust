"""Phase 5 callbacks match live DeepDiff."""

from conftest import require_deepdiff

require_deepdiff()

from deepdiff import DeepDiff as RealDeepDiff  # noqa: E402

from deepdiff_rust import DeepDiff  # noqa: E402


def test_exclude_obj_callback_matches() -> None:
    a, b = {"x": 1, "y": 2}, {"x": 9, "y": 2}

    def cb(obj, path):
        return path.endswith("['x']")

    assert DeepDiff(a, b, exclude_obj_callback=cb) == RealDeepDiff(a, b, exclude_obj_callback=cb)


def test_exclude_obj_callback_strict_matches() -> None:
    a, b = {"x": 1, "y": 2}, {"x": 9, "y": 3}

    def cb(obj, path):
        return isinstance(obj, int) and obj in (1, 9)

    assert DeepDiff(a, b, exclude_obj_callback_strict=cb) == RealDeepDiff(
        a, b, exclude_obj_callback_strict=cb
    )


def test_include_obj_callback_matches() -> None:
    a, b = {"x": 1, "y": 2}, {"x": 9, "y": 3}

    def cb(obj, path):
        return path.endswith("['x']")

    assert DeepDiff(a, b, include_obj_callback=cb) == RealDeepDiff(a, b, include_obj_callback=cb)


def test_include_obj_callback_strict_matches() -> None:
    a, b = {"x": 1, "y": 2}, {"x": 1, "y": 3}

    def cb(obj, path):
        return path.endswith("['y']")

    assert DeepDiff(a, b, include_obj_callback_strict=cb) == RealDeepDiff(
        a, b, include_obj_callback_strict=cb
    )
