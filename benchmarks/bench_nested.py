"""Nested-dict DeepDiff vs deepdiff-rust benchmark: `groups x records x fields` leaves.

    python benchmarks/bench_nested.py --groups 1000 --records 100 --fields 10

Both sides are built independently, so DeepDiff's `t1 is t2` shortcut never
skips a subtree. Wall time only; the reports are checked equal.
"""

from __future__ import annotations

import argparse
import statistics
import time

from deepdiff import DeepDiff as PythonDeepDiff
from deepdiff_rust import DeepDiff as RustDeepDiff


def make_tree(groups, records, fields, changed_every=0):
    """`{group: {record: {field: leaf}}}`; every `changed_every`-th leaf differs."""
    tree, n = {}, 0
    for g in range(groups):
        group = tree[f"group_{g}"] = {}
        for r in range(records):
            record = group[f"record_{r}"] = {}
            for f in range(fields):
                changed = changed_every and n % changed_every == 0
                record[f"field_{f}"] = -n if changed else n
                n += 1
    return tree


def as_lists(tree, reverse=False):
    """Each group becomes a list of its records, optionally in reverse order."""
    out = {}
    for name, group in tree.items():
        records = list(group.values())
        out[name] = records[::-1] if reverse else records
    return out


def timed(fn, repeats):
    samples, result = [], None
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn()
        samples.append(time.perf_counter() - start)
    return statistics.median(samples), result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--groups", type=int, default=1000)
    parser.add_argument("--records", type=int, default=100)
    parser.add_argument("--fields", type=int, default=10)
    parser.add_argument("--changed-every", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--python-repeats", type=int, default=1)
    parser.add_argument("--ignore-order", action="store_true")
    args = parser.parse_args()

    shape = (args.groups, args.records, args.fields)
    t1, t2 = make_tree(*shape), make_tree(*shape, changed_every=args.changed_every)
    print(f"leaves: {args.groups * args.records * args.fields:,}")

    cases = [("equal", t1, make_tree(*shape), {}), ("changed", t1, t2, {})]
    if args.ignore_order:
        lists = (as_lists(t1), as_lists(t2, reverse=True), {"ignore_order": True})
        cases.append(("ignore_order", *lists))
    for name, a, b, kw in cases:
        rust_s, rust = timed(lambda: RustDeepDiff(a, b, **kw), args.repeats)
        python_s, python = timed(lambda: PythonDeepDiff(a, b, **kw), args.python_repeats)
        assert rust == python, f"{name}: reports differ"
        changes = sum(map(len, rust.values()))
        print(
            f"{name:12} changes={changes:<6} deepdiff={python_s:8.2f}s "
            f"deepdiff_rust={rust_s:6.3f}s  x{python_s / rust_s:,.0f}"
        )


if __name__ == "__main__":
    main()
