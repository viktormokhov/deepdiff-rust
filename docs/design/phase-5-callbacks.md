# Phase 5: Python callbacks (hybrid)

Status: approved for implementation.
Target: DeepDiff 9.1.0 parity for callback options, without slowing the
no-callback path.

## Scope

In:

- `custom_operators`
- `iterable_compare_func`
- `exclude_obj_callback` / `exclude_obj_callback_strict`
- `include_obj_callback` / `include_obj_callback_strict`

Out (later phases):

- `hasher` (DeepHash / phase 6)
- Delta, DeepSearch, numpy
- `view='tree'` / `pretty()`

## Approach: hybrid dual walk

When every callback argument is absent, keep today's path unchanged:
convert live Python objects to `Value`, diff in Rust, report.

When any in-scope callback is present:

1. Still convert both sides to `Value` (needed for structural compare and
   `ignore_order` hashing).
2. Walk the same tree with live `PyAny` handles for the current `t1` / `t2`
   node, resolved by key/index/attribute from the parent objects.
3. Do **not** store Python objects inside `Value`.

At each node, match DeepDiff's `_diff` / `_skip_this` order:

1. `custom_operators`: for each operator, if `match(level)` then
   `give_up_diffing(level, diff_instance)`; on True, skip the default diff
   for that node (operator may already have reported).
2. `exclude_*` / `include_*` object callbacks with signatures
   `(obj, path)` as in DeepDiff; skip the node when they say so.
3. Otherwise run the normal Rust child diff. For iterables, when
   `iterable_compare_func` is set, use `(x, y, level)` to choose pairs
   the way DeepDiff does.

`Level` is a thin Python object with at least `t1`, `t2`, and `path()`.
`diff_instance` is our `DeepDiff` instance so operators can append to the
result the same way they do against stock DeepDiff.

## Compatibility notes

- Document supported callbacks in `docs/compatibility.md`.
- Document that `hasher` remains unsupported until DeepHash.
- Keep existing filter options (`exclude_paths`, etc.); object callbacks
  compose with them in DeepDiff order where practical.

## Verification

- Differential pytest cases vs live `deepdiff==9.1.0` for each callback.
- Existing suite must stay green; no-callback benches must not regress
  meaningfully (same code path as today).

## Implementation order

1. Wire kwargs through `_diff.py`, stubs, and the native binding.
2. Dual-walk plumbing + exclude/include object callbacks.
3. `iterable_compare_func`.
4. `custom_operators` + `Level`.
5. Tests, compatibility doc, commit; rebuild wheels on request.
