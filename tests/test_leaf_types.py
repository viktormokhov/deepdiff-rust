"""`bytes`, `Decimal`, `UUID` and `complex`, against DeepDiff 9.1.0."""

import json
from decimal import Decimal as D
from uuid import UUID

import pytest
from deepdiff import DeepDiff as RealDeepDiff

from deepdiff_rust import DeepDiff

U1, U2 = UUID(int=5), UUID("12345678-1234-5678-1234-567812345678")
CASES = [
    pytest.param([b"x", b"\xff", b"same"], [b"y", b"\xfe", b"same"], {}, id="bytes"),
    pytest.param(b"a\nb", b"a\nc", {}, id="bytes-multiline"),
    pytest.param(b"a", "a", {}, id="bytes-str"),
    pytest.param([b"a", b"\xff"], ["a", "x"], {"ignore_string_type_changes": True}, id="bytes-str-group"),
    pytest.param(b"AbC", b"abc", {"ignore_string_case": True}, id="bytes-case"),
    pytest.param([D("1.10"), D("2"), D("3.5")], [D("1.1"), D("2.0"), D("3.6")], {}, id="decimal"),
    pytest.param(D("1"), 1, {}, id="decimal-int"),
    pytest.param(
        [D("1"), D("0.5"), D("0.1")], [1, 0.5, 0.1], {"ignore_numeric_type_changes": True},
        id="decimal-group",
    ),
    pytest.param(D("0.5"), 0.5, {"ignore_type_in_groups": [(float, D)]}, id="decimal-exact-float"),
    pytest.param(D("0.1"), 0.1, {"ignore_type_in_groups": [(float, D)]}, id="decimal-inexact-float"),
    pytest.param(
        [D("1.2341"), D("5")], [D("1.2342"), D("6")], {"significant_digits": 3}, id="decimal-sig",
    ),
    pytest.param(D("1.0"), D("1.05"), {"math_epsilon": 0.1}, id="decimal-epsilon"),
    pytest.param([D("NaN"), D("Infinity")], [D("NaN"), D("-Infinity")], {}, id="decimal-special"),
    pytest.param([U1, U2], [UUID(int=6), U2], {}, id="uuid"),
    pytest.param(U1, str(U1), {}, id="uuid-str"),
    pytest.param(
        [U1, str(U2), "zz"], [str(U1), U2, U1], {"ignore_uuid_types": True}, id="uuid-ignore",
    ),
    pytest.param("{%s}" % U2, U2, {"ignore_uuid_types": True}, id="uuid-braces"),
    pytest.param([1 + 2j, 1j, -0.5 - 1e20j], [1 + 3j, 1j, -0.5 - 1e20j], {}, id="complex"),
    pytest.param(1 + 0j, 1, {"ignore_numeric_type_changes": True}, id="complex-int"),
    pytest.param(1.0001 + 2j, 1.0002 + 2j, {"significant_digits": 3}, id="complex-sig"),
    pytest.param({"k": b"x"}, {"k": D("1")}, {}, id="leaf-type-change"),
    pytest.param({D("1.5"): 1, 2j: 1}, {D("1.5"): 2, 2j: 2}, {}, id="leaf-keys"),
    pytest.param({b"a", D("1.5"), U1}, {b"b", D("1.5"), U2}, {}, id="leaf-set"),
    pytest.param(
        [b"a", D("1.5"), U1, 2j], [2j, U1, D("1.5"), b"b"], {"ignore_order": True}, id="order",
    ),
    pytest.param([D("1.10")], [D("1.1")], {"ignore_order": True}, id="order-decimal-text"),
    pytest.param(
        [D("1.0001"), D("2")], [D("2"), D("1.0002")],
        {"ignore_order": True, "significant_digits": 3}, id="order-sig",
    ),
    pytest.param(
        [D("1"), 2], [2.0, 1], {"ignore_order": True, "ignore_numeric_type_changes": True},
        id="order-numeric",
    ),
]


@pytest.mark.parametrize("verbose_level", [1, 2])
@pytest.mark.parametrize(("t1", "t2", "options"), CASES)
def test_leaf_matches_reference(t1, t2, options, verbose_level):
    actual = DeepDiff(t1, t2, verbose_level=verbose_level, **options)
    reference = RealDeepDiff(t1, t2, verbose_level=verbose_level, **options)

    # `repr` for a `NaN`, which never compares equal.
    assert actual == reference or repr(actual) == repr(reference)


def test_leaf_json_matches_reference():
    t1 = [b"x", b"\xff", D("1.10"), D("3"), D("12345678901234567890"), U1]
    t2 = [b"y", b"\xfe", D("1.2"), D("4"), D("12345678901234567891"), U2]

    assert json.loads(DeepDiff(t1, t2).to_json()) == json.loads(RealDeepDiff(t1, t2).to_json())
