# DeepDiff compatibility target

## Reference

- Reference package: `deepdiff==9.1.0`
- Python support target: CPython 3.10+
- Engine: forked from Onix 0.17.1
- Fork point: `85956c7f3c39d4e39697815714e92a21c0c74ce4`

## Current status

This repository contains the forked Onix Python adapter and Rust core. It is
**not yet a complete drop-in replacement** for DeepDiff.

Implemented, checked against `deepdiff==9.1.0`:

- `DeepDiff` is a `dict` of findings, like the reference result object.
- `ignore_order`, `max_depth` (an extension DeepDiff lacks), `verbose_level`
  0/1/2 with the reference default of 1, `view='text'`.
- `to_dict(verbose_level=...)`, `to_json(verbose_level=..., **json_dumps_kwargs)`,
  `affected_paths`, `affected_root_keys`, `t1`, `t2`.
- `type_changes` reports type objects in `to_dict()`, type names in `to_json()`.
- `exclude_paths`, `include_paths` (exact, bare keys, and `*`/`**` globs),
  `exclude_regex_paths`, `exclude_types`, `ignore_private_variables`.
- `significant_digits`, `number_format_notation`, `math_epsilon`,
  `use_log_scale`, `log_scale_similarity_threshold`, `ignore_nan_inequality`,
  `ignore_string_case`, `ignore_numeric_type_changes`,
  `ignore_string_type_changes`, `ignore_type_in_groups`,
  `ignore_type_subclasses`, `truncate_datetime` (datetimes),
  `ignore_uuid_types`, `use_enum_value`.
- `zip_ordered_iterables`, `threshold_to_diff_deeper`,
  `cutoff_distance_for_pairs`, `cutoff_intersection_for_pairs`,
  `get_deep_distance`, `group_by`, `group_by_sort_key`, `report_repetition`
  (`repetition_change`), `max_passes`, `max_diffs`,
  `exclude_obj_callback`, `exclude_obj_callback_strict`,
  `include_obj_callback`, `include_obj_callback_strict`,
  `iterable_compare_func`, `custom_operators`.
  Object include/exclude callbacks filter on the retain pass (same post-diff
  style as path filters). `iterable_compare_func` and `custom_operators`
  currently bridge to the installed `deepdiff` package for full walk semantics.
  `hasher` is not supported yet (DeepHash / phase 6).
- `bytes`, `decimal.Decimal`, `uuid.UUID` and `complex` values, keys and
  set members, under the numeric and string options above.

Known divergences: report key order follows sorted paths, not traversal
order; `affected_paths` and `affected_root_keys` are plain `set`s.
Filters drop findings after the diff rather than pruning it, so under
`ignore_order` an excluded part still takes part in pairing items;
`exclude_types` does not see inside set members; and
`ignore_private_variables=False` uncovers `__` dict keys but not an
object's `__` attributes.
`ignore_string_case` and `ignore_numeric_type_changes` do not fold dict
keys; `truncate_datetime` leaves `time` values alone (DeepDiff reports
them as seconds); the numpy members of DeepDiff's `numbers` group are left
out. A reported `Enum` or custom object renders as a dict of its attributes,
and an `IntEnum` diffs as a plain `int`. `bytes` dict keys (DeepDiff
crashes) and `UUID` dict keys (DeepDiff reports path `None`) get normal
paths. A `Decimal` rounds through its nearest `float` under
`significant_digits` and `math_epsilon`.
`max_diffs` counts steps where DeepDiff does, except inside the trial
diffs `ignore_order` runs to pair container items (one step each); it
does not log DeepDiff's "reached the max number of diffs" warning. Which
findings survive the limit in a multi-key dict differs, as DeepDiff walks
keys in `set` order.

Onix implements a useful subset of DeepDiff's core comparison API and converts
supported live Python objects directly into its native value model. Its documented
scope includes `None`, booleans, integers, floats, strings, dictionaries,
lists, tuples, sets, frozensets, `bytes`, `Decimal`, `UUID`, `complex`,
Python date/time types, enums, and many custom
objects by attributes. Unsupported types raise errors rather than being
silently coerced.

## Important upstream gaps

The pinned Onix revision documents these unsupported DeepDiff features:

- custom operators
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
