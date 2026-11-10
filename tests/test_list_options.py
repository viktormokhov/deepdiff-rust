"""Phase 4 list and pairing options diff like live DeepDiff."""

import json

import pytest
from conftest import require_deepdiff

require_deepdiff()

from deepdiff import DeepDiff as RealDeepDiff  # noqa: E402

from deepdiff_rs import DeepDiff  # noqa: E402

PEOPLE1 = [
    {"id": "AA", "name": "Joe", "last": "Nobody"},
    {"id": "BB", "name": "James", "last": "Blue"},
    {"id": "CC", "name": "Mike", "last": "Apple"},
]
PEOPLE2 = [
    {"id": "AA", "name": "Joe", "last": "Nobody"},
    {"id": "BB", "name": "James", "last": "Brown"},
    {"id": "CC", "name": "Mike", "last": "Apple"},
    {"id": "DD", "name": "Ann", "last": "Apple"},
]
WIDE1 = {"a": 1, "b": 2, "c": 3}
WIDE2 = {"a": 1, "x": 2, "y": 3, "z": 4}

IO = {"ignore_order": True}
CASES = [
    ([1, 2, 3, 4], [1, 3, 4, 5], {"zip_ordered_iterables": True}),
    ([1, 2, 3, 4], [1, 3, 4, 5], {}),
    ({"k": WIDE1}, {"k": WIDE2}, {}),
    ({"k": WIDE1}, {"k": WIDE2}, {"threshold_to_diff_deeper": 0}),
    ({"k": WIDE1}, {"k": WIDE2}, {"threshold_to_diff_deeper": 0.1}),
    ([[1, 2, 3, 9]], [[1, 2, 3, 4]], IO),
    ([[1, 2, 3, 9]], [[1, 2, 3, 4]], {**IO, "cutoff_distance_for_pairs": 0.05}),
    ([1, 2, [3, 4]], [5, 6, [3, 7]], {**IO, "cutoff_intersection_for_pairs": 1}),
    ([1, 2, [3, 4]], [5, 6, [3, 7]], IO),
    (PEOPLE1, PEOPLE2, {"group_by": "id"}),
    (PEOPLE1, PEOPLE2, {"group_by": ["last", "id"]}),
    (PEOPLE1, PEOPLE2, {"group_by": "last", "group_by_sort_key": "name"}),
    (PEOPLE1, PEOPLE2, {"group_by": lambda row: row["id"].lower()}),
    (PEOPLE1, PEOPLE2, {"group_by": "missing"}),
    ([1, 2], [1, 3], {"group_by": "id"}),
    ({"a": [1, 2, 3]}, {"a": [1, 2, 4]}, {"get_deep_distance": True}),
    ({"a": 1, "b": "x"}, {"a": 2, "c": "y"}, {"get_deep_distance": True}),
    (10, 12, {"get_deep_distance": True}),
    ([1, 2], [1, 2], {"get_deep_distance": True}),
    (PEOPLE1, PEOPLE2, {**IO, "get_deep_distance": True}),
]


@pytest.mark.parametrize("verbose_level", [1, 2])
@pytest.mark.parametrize(("t1", "t2", "kwargs"), CASES)
def test_list_option_matches_deepdiff(t1, t2, kwargs, verbose_level) -> None:
    kwargs = {"verbose_level": verbose_level, **kwargs}
    assert DeepDiff(t1, t2, **kwargs) == RealDeepDiff(t1, t2, **kwargs)


def test_deep_distance_is_in_json() -> None:
    ours = json.loads(DeepDiff([1, 2], [1, 3], get_deep_distance=True).to_json())
    assert ours == json.loads(RealDeepDiff([1, 2], [1, 3], get_deep_distance=True).to_json())


def test_cutoff_distance_out_of_range_raises_like_deepdiff() -> None:
    with pytest.raises(ValueError, match="cutoff_distance_for_pairs"):
        DeepDiff([1], [2], cutoff_distance_for_pairs=2)


def test_group_by_rewrites_t1_and_t2() -> None:
    diff = DeepDiff(PEOPLE1, PEOPLE2, group_by="id")
    assert diff.t1 == RealDeepDiff(PEOPLE1, PEOPLE2, group_by="id").t1
