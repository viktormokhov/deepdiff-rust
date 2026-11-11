# Phase 5 Callbacks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add DeepDiff 9.1.0 callback options via a hybrid dual walk that keeps the no-callback Rust path unchanged.

**Architecture:** When any callback is set, native diff walks `Value` as today and also carries live `PyAny` nodes for `t1`/`t2`. Node hooks run `custom_operators` then object include/exclude callbacks, then normal Rust child diffs; iterables may pair via `iterable_compare_func`. `Value` never stores Python objects.

**Tech Stack:** Rust (`deepdiff-core`, `deepdiff-python` / PyO3), Python package `deepdiff_rust`, pytest vs `deepdiff==9.1.0`.

## Global Constraints

- No-callback path must stay byte-identical and must not gain extra Python calls per node.
- Do not store `PyAny` inside `deepdiff_core::Value`.
- Match DeepDiff 9.1.0 callback signatures and skip/match semantics.
- `hasher` is out of scope (phase 6).
- Work on LLM host `/home/deploy/deepdiff-rust`, branch `fork-onix`; commit with author from `git log -1`.
- SSH exec commands must stay under ~1000 characters; use `~/sub.py` / small heredocs.

## File map

- Create: `python/deepdiff_rust/_callbacks.py` — `Level`, callback bundle
- Create: `tests/test_callbacks.py` — differential tests
- Modify: `python/deepdiff_rust/_diff.py`, `__init__.pyi`
- Modify: `crates/deepdiff-python/src/deepdiff.rs` + new `callbacks.rs`
- Modify: `crates/deepdiff-core` diff dispatch/array/ignore_order for hooks
- Modify: `docs/compatibility.md`

---

### Task 1: Python kwargs + Level

**Files:** Create `python/deepdiff_rust/_callbacks.py`, `tests/test_callbacks.py`; modify `_diff.py`, `__init__.pyi`

**Produces:** `Level(t1,t2,path_str)` with `.path()`; callback kwargs on `DeepDiff`

- [ ] Write `tests/test_callbacks.py` with differential cases for `exclude_obj_callback` (dict key path) vs live DeepDiff.
- [ ] Run pytest — FAIL on unexpected keyword.
- [ ] Add kwargs (default None) to `DeepDiff.__init__` and `.pyi`; add `Level` class; store callbacks on `self` but do not implement yet (test still fails on result mismatch).
- [ ] Commit: `feat: accept DeepDiff callback kwargs`

### Task 2: Object exclude/include dual-walk

**Files:** `deepdiff-python` (`deepdiff.rs`, new `callbacks.rs`), core `diff/dispatch.rs`, `_callbacks.py`, `_diff.py`

**Produces:** With callbacks, walk carries live `PyAny`; `hooks.skip_level(path,t1,t2)` mirrors DeepDiff object-callback branch of `_skip_this`. No-callback path unchanged.

- [ ] Tests for all four object callbacks vs live DeepDiff.
- [ ] Implement hooks + dual walk child resolution by key/index/attr.
- [ ] pytest PASS for object callbacks; full suite green.
- [ ] Commit: `feat: object exclude/include callbacks`

### Task 3: iterable_compare_func

**Files:** `diff/array.rs`, ignore_order pairing, `_callbacks.py`, tests

**Produces:** Pairing calls Python `(x, y, level) -> bool` when set.

- [ ] Differential tests for custom pairing / moves.
- [ ] Hook pair selection with `Level`.
- [ ] pytest PASS; commit `feat: iterable_compare_func`

### Task 4: custom_operators

**Files:** `_callbacks.py`, native hook at `diff_at` start, tests

**Produces:** `match(level)` then `give_up_diffing(level, diff_instance)`; True skips default diff. `diff_instance` is our Python `DeepDiff`.

- [ ] Test with a `BaseOperator` subclass that records findings.
- [ ] Implement; pytest PASS; commit `feat: custom_operators`

### Task 5: Docs and verify

- [ ] Update `docs/compatibility.md` (callbacks in; hasher out).
- [ ] Run `~/ddrs_final.sh` and `~/ddrs_clippy.sh` — green.
- [ ] Commit docs; offer wheel rebuild.
