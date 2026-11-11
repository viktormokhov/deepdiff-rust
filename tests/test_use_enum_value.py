"""`use_enum_value=True` diffs like live DeepDiff."""

import enum

import pytest
from conftest import require_deepdiff

require_deepdiff()

from deepdiff import DeepDiff as RealDeepDiff  # noqa: E402

from deepdiff_rust import DeepDiff  # noqa: E402


class C(enum.Enum):
    A = 1
    B = 2


class K(enum.Enum):
    A = 1


class S(str, enum.Enum):
    X = "x"
    Y = "y"


class I(enum.IntEnum):
    X = 1
    Y = 2


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
    ([C.A, 5], [7, C.B], {"ignore_order": True}),
    (S.X, "x", {}),
    (S.X, "y", {}),
    (S.X, S.Y, {}),
    (S.X, S.Y, {"use_enum_value": False}),
    (C.A, 1, {"use_enum_value": False}),
    (I.X, I.Y, {}),
    (I.X, 1, {}),
    (I.X, 1, {"use_enum_value": False}),
    (I.X, I.Y, {"use_enum_value": False}),
]


@pytest.mark.parametrize("verbose_level", [1, 2])
@pytest.mark.parametrize(("t1", "t2", "extra"), CASES)
def test_use_enum_value_matches_deepdiff(t1, t2, extra, verbose_level) -> None:
    kwargs = {"use_enum_value": True, "verbose_level": verbose_level, **extra}
    assert DeepDiff(t1, t2, **kwargs) == RealDeepDiff(t1, t2, **kwargs)
