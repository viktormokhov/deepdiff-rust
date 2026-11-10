import json

from deepdiff import DeepDiff as ReferenceDeepDiff
from deepdiff_rs import DeepDiff, diff_json


def test_deepdiff_import_and_dict_output():
    old = {"user": {"age": 30}}
    new = {"user": {"age": 31}, "active": True}
    result = DeepDiff(old, new)
    assert result
    assert result.to_dict() == ReferenceDeepDiff(old, new, verbose_level=2).to_dict()


def test_identical_values_are_falsy():
    assert not DeepDiff({"a": [1, 2]}, {"a": [1, 2]})


def test_ignore_order_matches_reference():
    old, new = [1, 2, 3], [3, 2, 1]
    assert DeepDiff(old, new, ignore_order=True).to_dict() == (
        ReferenceDeepDiff(old, new, ignore_order=True, verbose_level=2).to_dict()
    )


def test_json_fast_path():
    result = json.loads(diff_json('{"a":1}', '{"a":2}'))
    assert result["values_changed"]["root['a']"] == {
        "new_value": 2,
        "old_value": 1,
    }

def test_custom_object_attributes_match_reference():
    from dataclasses import dataclass

    @dataclass
    class Point:
        x: int
        y: int

    old, new = Point(1, 2), Point(1, 3)
    assert DeepDiff(old, new).to_dict() == ReferenceDeepDiff(
        old, new, verbose_level=2
    ).to_dict()


def test_nested_ignore_order_matches_reference():
    old = [{"id": 1, "tags": ["a", "b"]}, {"id": 2, "tags": ["c"]}]
    new = [{"id": 2, "tags": ["c"]}, {"id": 1, "tags": ["b", "a"]}]
    assert DeepDiff(old, new, ignore_order=True).to_dict() == ReferenceDeepDiff(
        old, new, ignore_order=True, verbose_level=2
    ).to_dict()
