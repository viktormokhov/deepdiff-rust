# Delta / extract implementation plan

## Goal

Ship scope-2 Delta: `to_dict`, `obj + delta` apply, `extract`. No pickle/flat.

## Files

- `python/deepdiff_rust/_path.py` — path parse + `extract`
- `python/deepdiff_rust/_delta.py` — `Delta`, `report_to_delta_dict`
- `python/deepdiff_rust/_diff.py` — `_to_delta_dict`, store `ignore_order`/`group_by`
- `python/deepdiff_rust/__init__.py` / `.pyi` — exports
- `tests/test_delta.py` — differential vs deepdiff 9.1.0
- `docs/design/delta.md` — design note

## Done

Implemented and tested (17/17 in `test_delta.py`). Version bump `0.1.3`.
