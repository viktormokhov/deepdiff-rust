# deepdiff-rust

A Rust-backed implementation of the core `DeepDiff` API, using the
[Onix](https://github.com/ksco92/onix) engine through a pinned Git submodule.

> **Status: early development.** This repository is not yet a complete
> replacement for the `deepdiff` package. The initial target is the
> `DeepDiff` comparison API and its live-Python-object conversion path.

## Quick start

Build from source with Rust, Python 3.10+, and Maturin:

```bash
git clone --recurse-submodules https://github.com/viktormokhov/deepdiff-rust.git
cd deepdiff-rust
python -m venv .venv
. .venv/bin/activate
python -m pip install maturin pytest
maturin develop --release
python -m pytest
```

The package exposes a separate import namespace so it can coexist with the reference DeepDiff package for differential testing:

```python
from deepdiff_rs import DeepDiff

diff = DeepDiff({"a": 1}, {"a": 2})
print(diff.to_dict())
print(diff.to_json())
```

The project distribution is named `deepdiff-rust`; its import package is `deepdiff_rs`. This lets the original `deepdiff` package remain installed as a differential-test oracle. A separate import-compatibility shim can be considered later, but should not shadow the reference package in the same environment.

## Architecture

- `vendor/onix`: upstream Onix source, pinned as a Git submodule to an exact
  revision. See [ADR 0001](docs/architecture/adr-0001-onix-core.md).
- `crates/deepdiff-python`: PyO3 extension and the public Python package
  integration.
- `python/deepdiff`: Python import facade.
- `tests`: Python API and differential tests.

The upstream Rust core performs structural comparison. The Python adapter
converts supported live Python objects into Onix's compact value model and
renders DeepDiff-compatible reports. JSON strings use a separate fast path
that parses, diffs, and serializes in Rust.

## Compatibility

The reference target is `deepdiff==9.1.0`. Compatibility is a work in progress,
not a blanket guarantee. The pinned Onix revision supports a useful subset of
DeepDiff's core behavior, including ordered comparisons and
`ignore_order=True`, but does not implement every DeepDiff option or module.

See [the compatibility matrix](docs/compatibility.md) and upstream
[known limitations](https://github.com/ksco92/onix#known-limitations).

## Performance

Upstream publishes reproducible benchmarks against DeepDiff 9.1.0, including
a one-million-key dictionary comparison. Those numbers are upstream results,
not yet independently reproduced in this repository and not a promise for
every workload. Our benchmarks will measure Python conversion, Rust diffing,
report rendering, end-to-end latency, and peak RSS separately.

## Development

```bash
cargo test --workspace
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
maturin develop --release
pytest -q
```

Always clone with `--recurse-submodules`. If the submodule is missing:

```bash
git submodule update --init --recursive
```

## Third-party code

The comparison engine and Python conversion modules currently reuse code from
Onix, Copyright (c) 2026 Rodrigo Carvajal, under the MIT License. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the upstream
[LICENSE](https://github.com/ksco92/onix/blob/main/LICENSE).

## License

The integration code in this repository is MIT-licensed. Third-party notices
and their respective licenses remain applicable.
