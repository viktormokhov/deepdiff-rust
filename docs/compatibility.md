# DeepDiff compatibility target

## Reference

- Reference package: `deepdiff==9.1.0`
- Python support target: CPython 3.10+
- Upstream engine under evaluation: Onix 0.17.1
- Pinned upstream revision: `85956c7f3c39d4e39697815714e92a21c0c74ce4`

## Current status

This repository is an integration scaffold. It is **not yet a drop-in
replacement** for DeepDiff. The current native implementation only compares
JSON-compatible values and does not preserve arbitrary Python object
semantics.

Onix implements a subset of DeepDiff's core comparison API. Its documented
scope includes `None`, booleans, integers, floats, strings, dictionaries,
lists, tuples, sets, frozensets, Python date/time types, and many custom
objects by attributes. Unsupported types raise errors rather than being
silently coerced.

## Important upstream gaps

The pinned Onix revision documents these unsupported DeepDiff features:

- `exclude_paths` and `include_paths`
- `significant_digits`
- custom operators
- `verbose_level != 2`
- Delta / patch functionality
- DeepHash and DeepSearch as full compatible modules

Additional semantic differences and resource limits are documented in
[Onix's Known limitations](https://github.com/ksco92/onix#known-limitations)
and its [golden-corpus notes](https://github.com/ksco92/onix/blob/85956c7f3c39d4e39697815714e92a21c0c74ce4/tests/golden/README.md).

## Compatibility test policy

Every option added to our public API must have:

1. A pinned reference test against real `deepdiff==9.1.0`.
2. Tests for both `to_dict()` and `to_json()` where applicable.
3. Tests for error type and error message when behavior is intentionally refused.
4. Regression coverage for nested and adversarial inputs.
5. A documented compatibility status: exact, intentionally different, or unsupported.

Golden output comparisons must normalize only representation details that are
explicitly documented. Do not broadly normalize away ordering or type
differences.

## Performance test policy

Benchmarks must separate:

- Python object conversion;
- Rust comparison;
- report construction and serialization;
- end-to-end Python API latency;
- peak resident memory.

Include at least: equal inputs, sparse changes, dense changes, flat million-key
dicts, large lists, deeply nested trees, and `ignore_order=True` workloads.
Never present a JSON-only core benchmark as the performance of live Python
objects.
