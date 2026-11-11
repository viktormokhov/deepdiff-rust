"""Delta / extract against deepdiff==9.1.0."""

import datetime
from copy import deepcopy

import pytest
from deepdiff import DeepDiff as RealDeepDiff
from deepdiff import Delta as RealDelta
from deepdiff import extract as real_extract

from deepdiff_rust import DeepDiff, Delta, extract


CASES = [
    pytest.param({"a": 1, "b": [1, 2]}, {"a": 2, "b": [1, 3], "c": 9}, {}, id="dict-list"),
    pytest.param([1, 2], [1, 2, 3], {}, id="list-add"),
    pytest.param([1, 2, 3], [1, 2], {}, id="list-remove"),
    pytest.param({"s": {1, 2}}, {"s": {2, 3}}, {}, id="set"),
    pytest.param({"x": 1}, {"x": "1"}, {}, id="type-change"),
    pytest.param(
        {"t": datetime.date(2020, 1, 1)},
        {"t": datetime.date(2021, 1, 1)},
        {},
        id="date",
    ),
]


@pytest.mark.parametrize(("t1", "t2", "options"), CASES)
def test_delta_to_dict_matches_reference(t1, t2, options):
    actual = Delta(DeepDiff(t1, t2, verbose_level=2, **options)).to_dict()
    reference = RealDelta(RealDeepDiff(t1, t2, verbose_level=2, **options)).to_dict()
    assert actual == reference


@pytest.mark.parametrize(("t1", "t2", "options"), CASES)
def test_delta_apply_matches_reference(t1, t2, options):
    ours = deepcopy(t1) + Delta(DeepDiff(t1, t2, verbose_level=2, **options))
    theirs = deepcopy(t1) + RealDelta(RealDeepDiff(t1, t2, verbose_level=2, **options))
    assert ours == theirs == t2


def test_bidirectional_to_dict_keeps_old_values():
    t1, t2 = {"a": 1}, {"a": 2}
    actual = Delta(
        DeepDiff(t1, t2, verbose_level=2),
        always_include_values=True,
        bidirectional=True,
    ).to_dict()
    reference = RealDelta(
        RealDeepDiff(t1, t2, verbose_level=2),
        always_include_values=True,
        bidirectional=True,
    ).to_dict()
    assert actual == reference
    assert actual["values_changed"]["root['a']"]["old_value"] == 1


def test_ignore_order_delta_to_dict_is_usable():
    t1 = {"name": "a", "tags": [1, 2]}
    t2 = {"name": "b", "tags": [1, 3], "extra": True}
    diff = DeepDiff(t1, t2, ignore_order=True, report_repetition=True, verbose_level=2)
    delta = Delta(diff, always_include_values=True, bidirectional=True)
    assert isinstance(delta.to_dict(), dict)
    assert delta.to_dict()


def test_extract_matches_reference():
    obj = {1: [{"2": "b"}, 3], 2: [4, 5]}
    path = "root[1][0]['2']"
    assert extract(obj, path) == real_extract(obj, path) == "b"


def test_ignore_order_without_report_repetition_is_refused():
    with pytest.raises(ValueError, match="report_repetition"):
        Delta(DeepDiff([1, 2], [2, 1], ignore_order=True))


def test_pickle_inputs_are_refused():
    with pytest.raises(NotImplementedError):
        Delta(diff=b"not-a-real-pickle")
