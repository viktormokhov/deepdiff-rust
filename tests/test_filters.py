"""Path and type filters, against DeepDiff 9.1.0."""

import re
from dataclasses import dataclass

import pytest
from deepdiff import DeepDiff as RealDeepDiff

from deepdiff_rust import DeepDiff


@dataclass
class Point:
    x: int
    y: int


NESTED_1 = {"a": {"b": 1, "c": [1, 2]}, "d": "x", "e": {"f": 1}, 5: "five"}
NESTED_2 = {"a": {"b": 2, "c": [1, 3], "n": 1}, "d": "y", "e": {"f": 2}, 5: "FIVE"}
USERS_1 = {"users": [{"name": "a", "pw": 1}, {"name": "b", "pw": 2}], "meta": {"pw": 1}}
USERS_2 = {"users": [{"name": "A", "pw": 9}, {"name": "b", "pw": 8}], "meta": {"pw": 2}}

N, U = (NESTED_1, NESTED_2), (USERS_1, USERS_2)
CASES = [
    pytest.param(*N, {"exclude_paths": "root['a']"}, id="exclude-exact"),
    pytest.param(*N, {"exclude_paths": ["d", "5"]}, id="exclude-bare-keys"),
    pytest.param(*N, {"exclude_paths": ["root['a']['c'][1]"]}, id="exclude-index"),
    pytest.param(*N, {"exclude_paths": ["root['a']['n']"]}, id="exclude-added-key"),
    pytest.param(*U, {"exclude_paths": ["root['users'][*]['pw']"]}, id="exclude-glob"),
    pytest.param(*U, {"exclude_paths": ["root[**]['pw']"]}, id="exclude-globstar"),
    pytest.param(*N, {"include_paths": "root['a']"}, id="include-exact"),
    pytest.param(*N, {"include_paths": ["e"]}, id="include-bare"),
    pytest.param(*N, {"include_paths": ["root['a']['b']"]}, id="include-deep"),
    pytest.param(*U, {"include_paths": ["root['users'][*]['name']"]}, id="include-glob"),
    pytest.param(*U, {"include_paths": ["root[**]['pw']"]}, id="include-globstar"),
    pytest.param(*N, {"exclude_regex_paths": r"\['b'\]|\[1\]"}, id="regex"),
    pytest.param(*N, {"exclude_regex_paths": [re.compile(r"root\['e'\]")]}, id="regex-compiled"),
    pytest.param(*N, {"exclude_types": [str]}, id="types-str"),
    pytest.param(*N, {"exclude_types": {list, int}}, id="types-list-int"),
    pytest.param({"a": 1}, {"a": "1"}, {"exclude_types": [str]}, id="types-either-side"),
    pytest.param(*N, {"include_paths": ["root['d']"], "exclude_types": [str]}, id="include-shadows-types"),
    pytest.param(Point(1, 2), Point(3, 4), {"exclude_paths": ["x"]}, id="object-attr"),
    pytest.param([1, 2, 3], [3, 2, 1, 4], {"exclude_paths": ["root[0]"]}, id="list"),
    pytest.param({"s": {1, 2}}, {"s": {2, 3}}, {"exclude_paths": ["root['s']"]}, id="set"),
    pytest.param({"__p": 1, "q": 1}, {"__p": 2, "q": 2}, {}, id="private-default"),
    pytest.param({"__p": 1}, {"__p": 2, "__n": 1}, {"ignore_private_variables": False}, id="private-off"),
    pytest.param({"x": {"__p": 1}}, {"x": {"__p": 2}}, {}, id="private-nested"),
    pytest.param([1, 2, 3], [4, 3, 2], {"ignore_order": True, "exclude_paths": ["root[0]"]}, id="ignore-order"),
    pytest.param({"a": {"b": 1}}, {"a": 5}, {"include_paths": ["root['a']['b']"]}, id="include-ancestor-type-change"),
    pytest.param(*U, {"include_paths": ["root['users'][0]"]}, id="include-index"),
    pytest.param({"s": {1, 2}, "t": 1}, {"s": {3}, "t": 2}, {"exclude_types": [set]}, id="types-set"),
]


@pytest.mark.parametrize("verbose_level", [1, 2])
@pytest.mark.parametrize(("t1", "t2", "options"), CASES)
def test_filter_matches_reference(t1, t2, options, verbose_level):
    actual = DeepDiff(t1, t2, verbose_level=verbose_level, **options)
    reference = RealDeepDiff(t1, t2, verbose_level=verbose_level, **options)

    assert actual == reference


def test_wildcard_path_must_start_at_root():
    with pytest.raises(ValueError, match="Wildcard paths must start with 'root'"):
        DeepDiff({}, {}, exclude_paths=["[*]"])
