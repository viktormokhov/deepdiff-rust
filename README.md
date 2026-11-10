# deepdiff-rust

A Rust-powered diff engine with Python bindings, targeting compatibility with
[DeepDiff](https://github.com/seperman/deepdiff).

> **Status: early development.** The current repository is a project scaffold.
> API compatibility and performance claims will be made only after differential
> tests against a pinned DeepDiff release and reproducible benchmarks.

## Goals

- Provide a fast Rust core for recursive structural comparison.
- Expose a Python API through PyO3 and build wheels with Maturin.
- Preserve Python type information where possible; avoid forcing arbitrary
  Python objects through JSON.
- Establish differential tests against the reference DeepDiff implementation.
- Measure runtime and peak memory on representative workloads, including
  million-element collections.

## Development

Prerequisites: stable Rust toolchain, Python 3.10+, and Maturin.

```bash
python -m pip install maturin pytest
maturin develop --manifest-path crates/deepdiff-python/Cargo.toml
pytest
cargo test --workspace
```

## Project layout

- `crates/deepdiff-core`: Python-independent comparison engine.
- `crates/deepdiff-python`: PyO3 extension module.
- `python/deepdiff_rust`: Python package facade.
- `tests`: Python API and differential tests.

## Compatibility policy

The initial target is the public `DeepDiff` API from DeepDiff 9.1.0. Full
compatibility is a goal, not an assumption. Unsupported options must fail
clearly rather than silently produce misleading results.

## License

License selection is pending an implementation and dependency audit. No code
from third-party projects is copied into this repository at this stage.
