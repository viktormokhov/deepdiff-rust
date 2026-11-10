"""Seeded random nested lists diff like live DeepDiff under `ignore_order`."""

import random

import pytest
from conftest import require_deepdiff

require_deepdiff()

from deepdiff import DeepDiff as RealDeepDiff  # noqa: E402

from deepdiff_rs import DeepDiff  # noqa: E402


def _gen(rnd, depth=0):
    r = rnd.random()
    if depth > 2 or r < 0.5:
        return rnd.choice([1, 2, 3, "a", "b", 1.5, None])
    if r < 0.8:
        return [_gen(rnd, depth + 1) for _ in range(rnd.randint(0, 5))]
    return {rnd.choice("xyz"): _gen(rnd, depth + 1) for _ in range(rnd.randint(0, 3))}


@pytest.mark.parametrize("report_repetition", [False, True])
@pytest.mark.parametrize("seed", range(3))
def test_random_lists_match_deepdiff(seed, report_repetition) -> None:
    rnd = random.Random(seed)
    kwargs = {"ignore_order": True, "get_deep_distance": True, "report_repetition": report_repetition}
    for _ in range(100):
        a = [_gen(rnd) for _ in range(rnd.randint(0, 6))]
        b = [_gen(rnd) for _ in range(rnd.randint(0, 6))]
        assert DeepDiff(a, b, **kwargs) == RealDeepDiff(a, b, **kwargs), (a, b)
