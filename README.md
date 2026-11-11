# deepdiff-rust

Rust-backed [DeepDiff](https://github.com/seperman/deepdiff) for Python.
Forked from [Onix](https://github.com/ksco92/onix) (`deepdiff-rs`) and extended
toward full `deepdiff==9.1.0` parity for the comparison API.

- **Distribution:** `deepdiff-rust`
- **Import:** `deepdiff_rust` (does not shadow PyPI `deepdiff` or `deepdiff-rs`)
- **Runtime deps:** none (CPython 3.10+)
- **Branch:** `fork-onix` is the active development line

```python
from deepdiff_rust import DeepDiff

print(DeepDiff({"a": 1, "b": [1, 2]}, {"a": 2, "b": [1, 3]}))
# {'values_changed': {"root['a']": {...}, "root['b'][1]": {...}}}
```

## Install

From a local wheel (Windows / manylinux x86_64 abi3):

```bash
pip install --force-reinstall --no-deps path/to/deepdiff_rust-0.1.0-*.whl
```

From source (Rust toolchain + Maturin):

```bash
git clone https://github.com/viktormokhov/deepdiff-rust.git
cd deepdiff-rust
git checkout fork-onix
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install maturin
maturin develop --release
```

## Status

**Core `DeepDiff(...)` comparison is largely done** and differentially tested
against live `deepdiff==9.1.0`. Not a complete drop-in for the whole DeepDiff
*package* yet (no DeepHash / DeepSearch / Delta).

### Supported (tested vs DeepDiff 9.1.0)

| Area | Options / behavior |
|---|---|
| Result API | `dict`-like result, `to_dict` / `to_json`, `affected_paths`, `affected_root_keys`, `t1` / `t2`, `verbose_level` 0/1/2 |
| Order | `ignore_order`, `zip_ordered_iterables`, pairing cutoffs, `threshold_to_diff_deeper`, `report_repetition`, `group_by` |
| Limits | `max_diffs`, `max_passes`, `max_depth` (extension beyond DeepDiff) |
| Numbers / strings | `significant_digits`, `math_epsilon`, `use_log_scale`, `ignore_nan_inequality`, `ignore_string_case`, type-ignore groups |
| Filters | `exclude_paths` / `include_paths` (incl. `*`/`**`), `exclude_regex_paths`, `exclude_types`, `ignore_private_variables` |
| Callbacks | `exclude_obj_callback`(+`_strict`), `include_obj_callback`(+`_strict`), `iterable_compare_func`, `custom_operators` |
| Types | `None`, bool, int, float, str, bytes, list/tuple/set/frozenset, dict, Decimal, UUID, complex, datetime/date/time/timedelta, Enum / IntEnum (`use_enum_value`), numpy int/float scalars + `ndarray`, many custom objects by attributes |
| Other | `get_deep_distance`, `view='tree'`, `pretty()`, `diff_json` (JSON fast path in Rust) |

Details and known divergences: [docs/compatibility.md](docs/compatibility.md).

### Not yet

- `DeepHash` / `hasher`, `DeepSearch`, `Delta` / patch
- numpy `bool_` / `datetime64` / complex scalars
- Onix extras we did not port: `diff_tables` (Arrow), `onix` CLI
- Some exotic report shapes for failed/opaque objects may still differ from DeepDiff

## vs `deepdiff-rs` (Onix) and `deepdiff`

| | `deepdiff` | `deepdiff-rs` (Onix) | **this package** |
|---|---|---|---|
| Engine | pure Python | Rust | Rust (Onix fork) |
| Import | `deepdiff` | `deepdiff_rs` | `deepdiff_rust` |
| Pip runtime deps | several | none (+ optional pyarrow) | none |
| Full DeepDiff option set | yes | core only | most comparison options |
| DeepHash / Delta / Search | yes | no | no (planned) |
| Arrow `diff_tables` | no | yes | no |

Keep stock `deepdiff` installed only if you want differential tests or a reference oracle.

## Architecture

- `crates/deepdiff-core` — comparison engine, paths, reports
- `crates/deepdiff-python` — PyO3 extension (`deepdiff_rust._native`)
- `python/deepdiff_rust` — public Python API
- `tests` — API + differential tests against `deepdiff==9.1.0`
- `docs/` — compatibility matrix and design notes

Live Python objects are converted into a native value model, diffed in Rust,
then rendered as DeepDiff-compatible reports. JSON strings can skip the
Python object round-trip via `diff_json`.

## Development

```bash
pip install -e ".[test]"   # pytest + deepdiff==9.1.0
cargo test --workspace
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
maturin develop --release
pytest -q
```

## Publishing to PyPI

Workflow [`.github/workflows/publish.yml`](.github/workflows/publish.yml) builds
abi3 wheels (Linux x86_64/aarch64, Windows x64, macOS Intel/ARM) plus an sdist.

### Secrets (GitHub → Settings → Secrets and variables → Actions)

| Secret | Purpose |
|---|---|
| `TEST_PYPI_API_TOKEN` | Upload to https://test.pypi.org |
| `PYPI_API_TOKEN` | Upload to https://pypi.org |

Create tokens on TestPyPI / PyPI (Account → API tokens). Store the raw token
value; maturin authenticates as user `__token__`.

### Dry run on TestPyPI

1. Register on https://test.pypi.org and create a token → secret
   `TEST_PYPI_API_TOKEN`.
2. **Actions → Publish → Run workflow** → target `testpypi`.
3. Install and smoke-test:

```bash
pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ deepdiff-rust==0.1.0
python -c "from deepdiff_rust import DeepDiff; print(DeepDiff({'a':1},{'a':2}))"
```

(`--extra-index-url` is only needed if a future release gains PyPI dependencies.)

### Production release

1. Version in `pyproject.toml` and `[workspace.package]` must match the tag
   without the leading `v` (e.g. `0.1.0` ↔ `v0.1.0`).
2. Push the tag (or run the workflow with target `pypi`):

```bash
git tag v0.1.0
git push origin v0.1.0
```

3. After the job finishes: `pip install deepdiff-rust`.

A version string can be uploaded to PyPI only once — fix mistakes with a new
version number.

## Third-party code

Comparison engine and Python conversion modules are forked from Onix,
Copyright (c) 2026 Rodrigo Carvajal, MIT. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [LICENSE-ONIX](LICENSE-ONIX).

## License

MIT. Upstream licenses in third-party notices still apply.
