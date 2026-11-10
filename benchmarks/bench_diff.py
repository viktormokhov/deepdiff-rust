"""End-to-end DeepDiff vs deepdiff-rust benchmark.

Run after installing both packages and building this project:
    python benchmarks/bench_diff.py --size 1000000 --repeats 3

This measures the live Python-object API, not only the Rust JSON fast path.
The report includes wall time and peak tracemalloc usage. Use an external RSS
sampler (for example /usr/bin/time -v) for process peak resident memory.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import tracemalloc
from typing import Any, Callable

from deepdiff import DeepDiff as PythonDeepDiff
from deepdiff_rs import DeepDiff as RustDeepDiff


def make_dict(size: int, changed_every: int) -> tuple[dict[str, Any], dict[str, Any]]:
    left = {f"key_{i}": {"id": i, "value": i, "active": i % 2 == 0} for i in range(size)}
    right = left.copy()
    for i in range(0, size, changed_every):
        right[f"key_{i}"] = {"id": i, "value": -i, "active": i % 2 == 0}
    return left, right


def measure(fn: Callable[[], Any], repeats: int) -> dict[str, float]:
    samples: list[float] = []
    peaks: list[int] = []
    for _ in range(repeats):
        tracemalloc.start()
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peaks.append(peak)
    return {
        "median_seconds": statistics.median(samples),
        "min_seconds": min(samples),
        "max_seconds": max(samples),
        "median_tracemalloc_peak_bytes": float(statistics.median(peaks)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=100_000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--changed-every", type=int, default=20)
    args = parser.parse_args()

    left, right = make_dict(args.size, args.changed_every)
    # Correctness precheck before timing.
    expected = PythonDeepDiff(left, right, verbose_level=2).to_dict()
    actual = RustDeepDiff(left, right).to_dict()
    if actual != expected:
        raise SystemExit("Refusing to benchmark: Python and Rust reports differ")

    results = {
        "python_deepdiff": measure(
            lambda: PythonDeepDiff(left, right, verbose_level=2), args.repeats
        ),
        "rust_deepdiff": measure(
            lambda: RustDeepDiff(left, right), args.repeats
        ),
    }
    results["metadata"] = {
        "size": args.size,
        "changed_every": args.changed_every,
        "repeats": args.repeats,
        "correctness": "matched",
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
