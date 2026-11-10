import json
from dataclasses import dataclass

import pytest
from deepdiff import DeepDiff as ReferenceDeepDiff

from deepdiff_rs import DeepDiff, diff_json


def assert_matches_reference(old, new, **kwargs):
    """Compare Rust implementation against DeepDiff 9.1.0."""
    actual = DeepDiff(old, new, **kwargs).to_dict()

    reference = ReferenceDeepDiff(
        old,
        new,
        verbose_level=2,
        **kwargs,
    ).to_dict()

    assert actual == reference


@pytest.mark.parametrize(
    ("old", "new"),
    [
        pytest.param(
            {"a": 1},
            {"a": 2},
            id="simple-value-change",
        ),
        pytest.param(
            {"a": 1},
            {"a": 1, "b": 2},
            id="dictionary-item-added",
        ),
        pytest.param(
            {"a": 1, "b": 2},
            {"a": 1},
            id="dictionary-item-removed",
        ),
        pytest.param(
            {"user": {"age": 30}},
            {"user": {"age": 31}},
            id="nested-value-change",
        ),
        pytest.param(
            [1, 2, 3],
            [1, 2, 4],
            id="list-item-changed",
        ),
        pytest.param(
            [1, 2],
            [1, 2, 3],
            id="list-item-added",
        ),
        pytest.param(
            [1, 2, 3],
            [1, 2],
            id="list-item-removed",
        ),
        pytest.param(
            100,
            "100",
            marks=pytest.mark.xfail(strict=True, reason="to_dict() reports type names, DeepDiff reports type objects"),
            id="type-change",
        ),
        pytest.param(
            {"a": [1, {"b": 2}]},
            {"a": [1, {"b": 3}]},
            id="deeply-nested-change",
        ),
        pytest.param(
            {"a": None},
            {"a": 0},
            marks=pytest.mark.xfail(strict=True, reason="to_dict() reports type names, DeepDiff reports type objects"),
            id="none-to-zero",
        ),
    ],
)
def test_basic_diff_matches_reference(old, new):
    assert_matches_reference(old, new)


@pytest.mark.parametrize(
    ("old", "new", "kwargs"),
    [
        pytest.param(
            [1, 2, 3],
            [3, 2, 1],
            {"ignore_order": True},
            id="ignore-order",
        ),
        pytest.param(
            [{"id": 1}, {"id": 2}],
            [{"id": 2}, {"id": 1}],
            {"ignore_order": True},
            id="nested-ignore-order",
        ),
        pytest.param(
            [1, 1, 2],
            [1, 2, 2],
            {"ignore_order": True},
            id="ignore-order-with-duplicates",
        ),
    ],
)
def test_options_match_reference(old, new, kwargs):
    assert_matches_reference(old, new, **kwargs)


def test_identical_values_are_falsy():
    assert not DeepDiff({"a": [1, 2]}, {"a": [1, 2]})


def test_json_fast_path():
    result = json.loads(diff_json('{"a":1}', '{"a":2}'))

    assert result["values_changed"]["root['a']"] == {
        "new_value": 2,
        "old_value": 1,
    }


def test_custom_object_attributes_match_reference():
    @dataclass
    class Point:
        x: int
        y: int

    old, new = Point(1, 2), Point(1, 3)

    assert_matches_reference(old, new)


def test_nested_ignore_order_matches_reference():
    old = [
        {"id": 1, "tags": ["a", "b"]},
        {"id": 2, "tags": ["c"]},
    ]

    new = [
        {"id": 2, "tags": ["c"]},
        {"id": 1, "tags": ["b", "a"]},
    ]

    assert_matches_reference(old, new, ignore_order=True)
