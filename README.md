# deepdiff-rust

A Rust implementation of the `DeepDiff` API for Python. The engine started
as a fork of [Onix](https://github.com/ksco92/onix) and is maintained here.

> **Status: early development.** This repository is not yet a complete
> replacement for the `deepdiff` package. The initial target is the
> `DeepDiff` comparison API and its live-Python-object conversion path.

## Quick start

Build from source with Rust, Python 3.10+, and Maturin:

```bash
git clone https://github.com/viktormokhov/deepdiff-rust.git
cd deepdiff-rust
python -m venv .venv
. .venv/bin/activate
python -m pip install maturin pytest
maturin develop --release
python -m pytest
```

The package exposes a separate import namespace so it can coexist with the reference DeepDiff package for differential testing:

```python
from deepdiff_rust import DeepDiff

diff = DeepDiff({"a": 1}, {"a": 2})
print(diff.to_dict())
print(diff.to_json())
```

The project distribution is named `deepdiff-rust`; its import package is `deepdiff_rust`. This lets the original `deepdiff` package remain installed as a differential-test oracle. A separate import-compatibility shim can be considered later, but should not shadow the reference package in the same environment.

## Architecture

- `crates/deepdiff-core`: comparison engine, paths, reports (forked from Onix,
  see [ADR 0002](docs/architecture/adr-0002-fork-onix.md)).
- `crates/deepdiff-python`: PyO3 extension and the public Python package
  integration.
- `python/deepdiff_rust`: Python import facade.
- `tests`: Python API and differential tests.

The Rust core performs structural comparison. The Python adapter
converts supported live Python objects into the core value model and
renders DeepDiff-compatible reports. JSON strings use a separate fast path
that parses, diffs, and serializes in Rust.

## Compatibility

The reference target is `deepdiff==9.1.0`. Compatibility is a work in progress,
not a blanket guarantee. The target is full parity; see [the compatibility matrix](docs/compatibility.md)
for what is implemented today.

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

## Third-party code

The comparison engine and Python conversion modules are forked from
Onix, Copyright (c) 2026 Rodrigo Carvajal, under the MIT License. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the upstream
[LICENSE-ONIX](LICENSE-ONIX).

## License

The integration code in this repository is MIT-licensed. Third-party notices
and their respective licenses remain applicable.
