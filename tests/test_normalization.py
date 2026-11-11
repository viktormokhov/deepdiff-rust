"""Value-normalization options, against DeepDiff 9.1.0."""

import datetime
from collections import OrderedDict

import pytest
from deepdiff import DeepDiff as RealDeepDiff

from deepdiff_rust import DeepDiff

F1, F2 = [1.0001, 2.5, 3.14159, -0.0004], [1.0002, 2.5004, 3.14161, 0.0003]
CASES = [
    pytest.param(F1, F2, {"significant_digits": 3}, id="sig-3"),
    pytest.param(F1, F2, {"significant_digits": 4}, id="sig-4"),
    pytest.param(F1, F2, {"significant_digits": 0}, id="sig-0"),
    pytest.param([10, 1234.5], [11, 1234.4], {"significant_digits": 1}, id="sig-ints"),
    pytest.param(
        [123456.7, 0.00012345], [123457.1, 0.00012349],
        {"significant_digits": 2, "number_format_notation": "e"}, id="sig-e",
    ),
    pytest.param({"a": 1.0, "b": 2.0}, {"a": 1.05, "b": 2.2}, {"math_epsilon": 0.1}, id="epsilon"),
    pytest.param([100.0, 1.0], [105.0, 2.0], {"use_log_scale": True}, id="log-scale"),
    pytest.param(
        [100.0, 1.0], [150.0, 2.0],
        {"use_log_scale": True, "log_scale_similarity_threshold": 0.5}, id="log-threshold",
    ),
    pytest.param({"x": float("nan"), "y": 1.0}, {"x": float("nan"), "y": 2.0}, {"ignore_nan_inequality": True}, id="nan"),
    pytest.param({"s": "Hello", "t": "A"}, {"s": "hello", "t": "b"}, {"ignore_string_case": True}, id="case"),
    pytest.param(["Ab", "c"], ["aB", "D"], {"ignore_string_case": True}, id="case-list"),
    pytest.param({"a": 1, "b": 2}, {"a": 1.0, "b": 2.5}, {"ignore_numeric_type_changes": True}, id="numeric"),
    pytest.param([1, 2, 3], [1.0, 2.0, 4.0], {"ignore_numeric_type_changes": True}, id="numeric-list"),
    pytest.param({"a": 1}, {"a": 1.0}, {"ignore_type_in_groups": [(int, float)]}, id="groups"),
    pytest.param({"a": 1}, {"a": "1"}, {"ignore_type_in_groups": [(int, str)]}, id="groups-int-str"),
    pytest.param({"a": None}, {"a": 1}, {"ignore_type_in_groups": [(int, None)]}, id="groups-none"),
    pytest.param({"a": [1, 2]}, {"a": (1, 3)}, {"ignore_type_in_groups": [(list, tuple)]}, id="groups-list-tuple"),
    pytest.param({"a": {1}}, {"a": frozenset({2})}, {"ignore_type_in_groups": [(set, frozenset)]}, id="groups-sets"),
    pytest.param(OrderedDict(a=1), {"a": 2}, {"ignore_type_in_groups": [(dict, OrderedDict)]}, id="groups-dicts"),
    pytest.param(
        OrderedDict(a=1), {"a": 1},
        {"ignore_type_in_groups": [dict, OrderedDict], "ignore_type_subclasses": True}, id="groups-exact",
    ),
    pytest.param(True, 1, {"ignore_numeric_type_changes": True}, id="bool-int"),
    pytest.param(datetime.date(2020, 1, 1), 5, {"ignore_numeric_type_changes": True}, id="date-number"),
    pytest.param([1.0001, 2.0], [2.0, 1.0002], {"ignore_order": True, "significant_digits": 3}, id="order-sig"),
    pytest.param(["A", "b"], ["B", "a"], {"ignore_order": True, "ignore_string_case": True}, id="order-case"),
    pytest.param([1, 2], [2.0, 1.0], {"ignore_order": True, "ignore_numeric_type_changes": True}, id="order-numeric"),
    pytest.param({1.0001, 2.0}, {1.0002, 2.0}, {"significant_digits": 3}, id="set-sig"),
]


@pytest.mark.parametrize("verbose_level", [1, 2])
@pytest.mark.parametrize(("t1", "t2", "options"), CASES)
def test_option_matches_reference(t1, t2, options, verbose_level):
    actual = DeepDiff(t1, t2, verbose_level=verbose_level, **options)
    reference = RealDeepDiff(t1, t2, verbose_level=verbose_level, **options)

    assert actual == reference


def test_negative_significant_digits_is_refused():
    with pytest.raises(ValueError, match="significant_digits must be None or a non-negative integer"):
        DeepDiff(1, 2, significant_digits=-1)


def test_unknown_number_format_notation_is_refused():
    with pytest.raises(ValueError, match="number_format_notation got invalid value of g"):
        DeepDiff(1.0, 2.0, significant_digits=2, number_format_notation="g")


DT = datetime.datetime
TRUNCATE_CASES = [
    pytest.param(DT(2020, 1, 1, 10, 30, 15, 500), DT(2020, 1, 1, 10, 30, 15, 900), "second", id="second"),
    pytest.param(DT(2020, 1, 1, 10, 30, 15), DT(2020, 1, 1, 10, 30, 45), "minute", id="minute"),
    pytest.param(DT(2020, 1, 1, 10, 30), DT(2020, 1, 1, 11, 30), "hour", id="hour-changed"),
    pytest.param(DT(2020, 1, 1, 10), DT(2020, 1, 2, 11), "day", id="day-changed"),
]

TIME = datetime.time
TRUNCATE_TIME_CASES = [
    pytest.param(TIME(10, 30, 15), TIME(10, 30, 45), "second", id="time-second"),
    pytest.param(TIME(10, 30, 15), TIME(10, 30, 45), "minute", id="time-minute-equal"),
    pytest.param(TIME(10, 30), TIME(11, 30), "hour", id="time-hour"),
    pytest.param(TIME(10, 30), TIME(11, 30), "day", id="time-day-equal"),
]


@pytest.mark.parametrize(("t1", "t2", "unit"), TRUNCATE_CASES)
def test_truncate_datetime_matches_reference(t1, t2, unit):
    actual = DeepDiff({"t": t1}, {"t": t2}, truncate_datetime=unit, verbose_level=2)

    assert actual == RealDeepDiff({"t": t1}, {"t": t2}, truncate_datetime=unit, verbose_level=2)


@pytest.mark.parametrize(("t1", "t2", "unit"), TRUNCATE_TIME_CASES)
def test_truncate_time_matches_reference(t1, t2, unit):
    actual = DeepDiff({"t": t1}, {"t": t2}, truncate_datetime=unit, verbose_level=2)

    assert actual == RealDeepDiff({"t": t1}, {"t": t2}, truncate_datetime=unit, verbose_level=2)


def test_unknown_truncate_datetime_is_refused():
    with pytest.raises(ValueError, match="truncate_datetime must be second, minute, hour or day"):
        DeepDiff(1, 2, truncate_datetime="week")
