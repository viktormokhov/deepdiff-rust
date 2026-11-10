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
