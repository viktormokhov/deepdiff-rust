# ADR 0001: Use Onix as the initial Rust diff engine

- Status: Superseded by [ADR 0002](adr-0002-fork-onix.md)
- Date: 2026-11-10
- Upstream: https://github.com/ksco92/onix
- Pinned revision: 85956c7f3c39d4e39697815714e92a21c0c74ce4
- Upstream version at pin: 0.17.1

## Context

Reimplementing DeepDiff's recursive comparison, Python value semantics,
path rendering, list matching, and unordered matching from scratch would
duplicate substantial existing work. Onix already has a Rust core, PyO3
conversion layer, a differential golden corpus against DeepDiff 9.1.0,
and reproducible benchmarks.

## Decision

Track upstream Onix as a Git submodule at `vendor/onix`, pinned to the exact
revision above. Do not silently copy upstream code or track its moving main
branch. Preserve the upstream MIT license and copyright notice.

Our project owns the integration layer, packaging, compatibility policy,
additional tests, and any separately maintained patches. Upstream changes are
pulled deliberately and reviewed before the pin is advanced.

The first target is the core `DeepDiff` API, not the entire DeepDiff product.
The current upstream API supports live Python objects and JSON text but is
explicitly a subset: `ignore_order` and a depth option are exposed, while
many options and modules remain unsupported.

## Consequences

- We inherit a mature diff engine and its existing correctness corpus.
- We must preserve attribution and include upstream license notices.
- We must document every accepted semantic divergence and unsupported option.
- We must not claim full DeepDiff compatibility until the differential suite
  demonstrates it.
- We must measure the complete Python call path, including conversion and
  report rendering, not only Rust-core time.

## Known upstream constraints to carry into our test plan

- `ignore_order` pairing is quadratic in unpaired elements per list level.
- Ordered scalar sequence matching and multi-line string diffing can be
  quadratic in input length.
- JSON text parsing has a numeric limitation for integers beyond the
  `i64`/`u64` range.
- Some Python types and handlers are refused; the exact supported set is
  documented upstream.
- The project deliberately chooses deterministic behavior where Python set
  iteration order makes DeepDiff output process-dependent.

These constraints are not automatically defects; they are explicit
compatibility and resource-boundary decisions that our adapter must expose.

## Revisit when

- Upstream changes its public API or value model.
- A required production workload hits a documented limitation.
- The differential suite shows a regression after an upstream revision bump.
