import json

from deepdiff import DeepDiff, diff_json


def test_deepdiff_import_and_dict_output():
    result = DeepDiff({"user": {"age": 30}}, {"user": {"age": 31}, "active": True})
    assert result
    assert result.to_dict()["values_changed"]["root['user']['age']"] == {
        "new_value": 31,
        "old_value": 30,
    }
    assert "dictionary_item_added" in result.to_dict()


def test_identical_values_are_falsy():
    assert not DeepDiff({"a": [1, 2]}, {"a": [1, 2]})


def test_ignore_order():
    assert not DeepDiff([1, 2, 3], [3, 2, 1], ignore_order=True)


def test_json_fast_path():
    result = json.loads(diff_json('{"a":1}', '{"a":2}'))
    assert result["values_changed"]["root['a']"] == {
        "new_value": 2,
        "old_value": 1,
    }
