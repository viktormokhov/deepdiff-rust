# ADR 0002: Fork Onix into this repository

- Status: Accepted
- Date: 2026-11-10
- Supersedes: [ADR 0001](adr-0001-onix-core.md)
- Forked from: https://github.com/ksco92/onix at `85956c7f3c39d4e39697815714e92a21c0c74ce4` (0.17.1)

## Context

The goal is full `deepdiff==9.1.0` feature parity. Most missing features
(`exclude_paths`, `significant_digits`, callbacks, `verbose_level`, Delta,
DeepHash, DeepSearch) need changes in the core engine and the Python
conversion layer, not only in an adapter around a pinned submodule.

## Decision

Own the code. `onix-core` lives in `crates/deepdiff-core`, the PyO3
adapter modules in `crates/deepdiff-python/src`, the golden corpus in
`tests/golden`, and its tooling in `scripts/`. The Arrow table diff and the
CLI are not carried over. Upstream is no longer tracked; useful upstream
fixes are ported by hand.

## Consequences

- The Onix MIT notice is kept in `LICENSE-ONIX` and `THIRD_PARTY_NOTICES.md`.
- Compatibility is proven by the golden corpus and differential tests
  against real DeepDiff; every new option adds golden cases.
