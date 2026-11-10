"""verbose_level, the dict-shaped result and its helpers, against DeepDiff 9.1.0."""

import json
from collections import OrderedDict, namedtuple
from dataclasses import dataclass

import pytest
from deepdiff import DeepDiff as RealDeepDiff

from deepdiff_rust import DeepDiff


@dataclass
class Point:
    x: int
    y: int


Pair = namedtuple("Pair", "a b")

CASES = [
    pytest.param({"a": 1, "b": 2}, {"a": 2, "c": 3}, id="dict"),
    pytest.param({"t": 1, "n": None}, {"t": "1", "n": 0}, id="type-change"),
    pytest.param([1, 2, 3], [3, 1], id="list"),
    pytest.param({"s": {1, 2}}, {"s": {2, 3}}, id="set"),
    pytest.param({"m": "x\ny"}, {"m": "x\nz"}, id="multiline"),
    pytest.param(Point(1, 2), Point(1, 3), id="object"),
    pytest.param({"p": Pair(1, 2)}, {"p": (1, 2)}, id="namedtuple-to-tuple"),
    pytest.param({"o": OrderedDict(a=1)}, {"o": {"a": 1}}, id="dict-subclass"),
    pytest.param({"f": 1.5}, {"f": 1}, id="float-to-int"),
    pytest.param({1: [1, {"x": 1}]}, {1: [1, {"x": 2}], 2: 2}, id="int-keys"),
]


@pytest.mark.parametrize("verbose_level", [0, 1, 2])
@pytest.mark.parametrize(("t1", "t2"), CASES)
def test_report_matches_reference(t1, t2, verbose_level):
    actual = DeepDiff(t1, t2, verbose_level=verbose_level)
    reference = RealDeepDiff(t1, t2, verbose_level=verbose_level)

    assert actual == reference
    assert actual.to_dict() == reference.to_dict()
    assert json.loads(actual.to_json()) == json.loads(reference.to_json())


@pytest.mark.parametrize(("t1", "t2"), CASES)
def test_default_verbose_level_is_one(t1, t2):
    assert DeepDiff(t1, t2) == RealDeepDiff(t1, t2)


@pytest.mark.parametrize("verbose_level", [0, 2])
@pytest.mark.parametrize(("t1", "t2"), CASES)
def test_render_time_verbose_level_override(t1, t2, verbose_level):
    actual = DeepDiff(t1, t2)
    reference = RealDeepDiff(t1, t2)

    assert actual.to_dict(verbose_level=verbose_level) == reference.to_dict(verbose_level=verbose_level)
    assert json.loads(actual.to_json(verbose_level=verbose_level)) == json.loads(
        reference.to_json(verbose_level=verbose_level)
    )


@pytest.mark.parametrize(("t1", "t2"), CASES)
def test_affected_paths_and_root_keys_match_reference(t1, t2):
    actual = DeepDiff(t1, t2)
    reference = RealDeepDiff(t1, t2)

    assert actual.affected_paths == set(reference.affected_paths)
    assert actual.affected_root_keys == set(reference.affected_root_keys)


def test_result_is_a_dict():
    diff = DeepDiff({"a": 1}, {"a": 2})

    assert isinstance(diff, dict)
    assert diff["values_changed"]["root['a']"] == {"new_value": 2, "old_value": 1}
    assert not DeepDiff([1], [1])
    assert (diff.t1, diff.t2) == ({"a": 1}, {"a": 2})


def test_to_json_passes_json_dumps_kwargs():
    diff = DeepDiff({"a": 1}, {"a": 2})

    assert diff.to_json(indent=2) == RealDeepDiff({"a": 1}, {"a": 2}).to_json(indent=2)


def test_invalid_verbose_level_is_refused_like_deepdiff():
    with pytest.raises(ValueError, match="verbose_level should be 0, 1, or 2."):
        DeepDiff(1, 2, verbose_level=3)


def test_unsupported_view_is_refused():
    with pytest.raises(NotImplementedError, match="view='tree'"):
        DeepDiff(1, 2, view="tree")
