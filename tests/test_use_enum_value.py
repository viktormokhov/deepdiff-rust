"""`use_enum_value=True` diffs like live DeepDiff."""

import enum

import pytest
from conftest import require_deepdiff

require_deepdiff()

from deepdiff import DeepDiff as RealDeepDiff  # noqa: E402

from deepdiff_rs import DeepDiff  # noqa: E402


class C(enum.Enum):
    A = 1
    B = 2


class K(enum.Enum):
    A = 1


class S(str, enum.Enum):
    X = "x"


# A reported custom object renders as a dict (docs/compatibility.md).
_RENDERS_OBJECT = pytest.mark.xfail(strict=True, reason="an Enum old_value renders as a dict")

CASES = [
    (C.A, C.B, {}),
    (C.A, 1, {}),
    (C.A, 2, {}),
    (C.A, "1", {}),
    (C.A, 1.0, {}),
    (C.A, K.A, {}),
    ({"k": C.A}, {"k": 1}, {}),
    ({"k": C.A}, {"k": 3}, {}),
    ([C.A, 2], [1, C.B], {}),
    ([C.A, 2], [1, C.B], {"ignore_order": True}),
    pytest.param([C.A, 5], [7, C.B], {"ignore_order": True}, marks=_RENDERS_OBJECT),
    (S.X, "x", {}),
    (S.X, "y", {}),
    pytest.param(C.A, 1, {"use_enum_value": False}, marks=_RENDERS_OBJECT),
]


@pytest.mark.parametrize("verbose_level", [1, 2])
@pytest.mark.parametrize(("t1", "t2", "extra"), CASES)
def test_use_enum_value_matches_deepdiff(t1, t2, extra, verbose_level) -> None:
    kwargs = {"use_enum_value": True, "verbose_level": verbose_level, **extra}
    assert DeepDiff(t1, t2, **kwargs) == RealDeepDiff(t1, t2, **kwargs)
