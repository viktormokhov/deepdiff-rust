# deepdiff-rust

Rust-backed [DeepDiff](https://github.com/seperman/deepdiff) for Python.
Forked from [Onix](https://github.com/ksco92/onix) (`deepdiff-rs`) and extended
toward `deepdiff==9.1.0` parity for the comparison API.

| | |
|---|---|
| PyPI | [`deepdiff-rust`](https://pypi.org/project/deepdiff-rust/) |
| Import | `deepdiff_rust` (does not shadow `deepdiff` / `deepdiff-rs`) |
| Runtime deps | none |
| Python | CPython 3.10+ (abi3 wheels) |
| Version | 0.1.5 |

```python
from deepdiff_rust import DeepDiff

print(DeepDiff({"a": 1, "b": [1, 2]}, {"a": 2, "b": [1, 3]}))
# {'values_changed': {"root['a']": {...}, "root['b'][1]": {...}}}
```

## Install

```bash
pip install deepdiff-rust
```

From source (Rust toolchain + [Maturin](https://www.maturin.rs/)):

```bash
git clone https://github.com/viktormokhov/deepdiff-rust.git
cd deepdiff-rust
git checkout fork-onix
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install maturin
maturin develop --release
```

## Status

Core `DeepDiff(...)` comparison is in place and differentially tested against
`deepdiff==9.1.0`. `Delta` / patch apply and `extract` are available (no
pickle/flat serialization yet). Still missing: DeepHash / DeepSearch.

### Supported (vs DeepDiff 9.1.0)

| Area | Options / behavior |
|---|---|
| Result API | dict-like result, `to_dict` / `to_json` (`default_mapping`), `affected_paths`, `affected_root_keys`, `t1` / `t2`, `verbose_level` 0/1/2 |
| Order | `ignore_order`, `zip_ordered_iterables`, pairing cutoffs, `threshold_to_diff_deeper`, `report_repetition`, `group_by` |
| Limits | `max_diffs`, `max_passes`, `max_depth` (extension beyond DeepDiff) |
| Numbers / strings | `significant_digits`, `math_epsilon`, `use_log_scale`, `ignore_nan_inequality`, `ignore_string_case`, type-ignore groups |
| Filters | `exclude_paths` / `include_paths` (`*`/`**`), `exclude_regex_paths`, `exclude_types`, `ignore_private_variables` |
| Callbacks | `exclude_obj_callback`(+`_strict`), `include_obj_callback`(+`_strict`), `iterable_compare_func`, `custom_operators` |
| Types | `None`, bool, int, float, str, bytes, list/tuple/set/frozenset, dict, Decimal, UUID, complex, datetime/date/time/timedelta, Enum / IntEnum (`use_enum_value`), numpy int/float/`bool_`/`datetime64`/complex scalars + `ndarray`, many custom objects by attributes |
| Other | `truncate_datetime` (datetime + time), `get_deep_distance`, `view='tree'`, `pretty()`, `diff_json`, `Delta` / `extract` |

Known divergences: [docs/compatibility.md](docs/compatibility.md).

### Not yet

- `DeepHash` / `hasher`, `DeepSearch`
- Delta pickle default / flat_dicts / flat_rows / file loaders (pass `deserializer=` / `serializer=` for JSON)
- Onix extras not ported: `diff_tables` (Arrow), `onix` CLI
- Some exotic report shapes for opaque/failed objects may still differ

## vs DeepDiff and Onix

| | `deepdiff` | `deepdiff-rs` (Onix) | **deepdiff-rust** |
|---|---|---|---|
| Engine | pure Python | Rust | Rust (Onix fork) |
| Import | `deepdiff` | `deepdiff_rs` | `deepdiff_rust` |
| Runtime deps | several | none (+ optional pyarrow) | none |
| Comparison options | full | core | most |
| DeepHash / Delta / Search | yes | no | Delta+extract (no pickle/flat); no Hash/Search |
| Arrow `diff_tables` | no | yes | no |

Keep stock `deepdiff` only if you need it as a reference oracle or for tests.

## Layout

- `crates/deepdiff-core` — comparison engine
- `crates/deepdiff-python` — PyO3 extension (`deepdiff_rust._native`)
- `python/deepdiff_rust` — public Python API
- `tests` — API + differential tests vs `deepdiff==9.1.0`
- `docs/` — compatibility notes

## Development

Active branch: `fork-onix`.

```bash
pip install -e ".[test]"
cargo test --workspace
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
maturin develop --release
pytest -q
```

## Releasing

Bump `version` in `pyproject.toml` and `[workspace.package]`, then tag
`vX.Y.Z` and push. [`.github/workflows/publish.yml`](.github/workflows/publish.yml)
builds abi3 wheels (Linux x86_64/aarch64, Windows x64, macOS Intel/ARM) + sdist
and uploads to PyPI. Manual dry-run: Actions → Publish → `testpypi`.

## Third-party / license

MIT. Comparison engine and Python conversion modules are forked from Onix,
Copyright (c) 2026 Rodrigo Carvajal, MIT — see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [LICENSE-ONIX](LICENSE-ONIX).
