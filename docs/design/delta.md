# Delta / patch / extract (phase)

Status: approved scope **2** — apply + `to_dict` + `extract`, no pickle/flat.

## Public API

```python
from deepdiff_rust import DeepDiff, Delta, DeltaError, extract

diff = DeepDiff(t1, t2)
delta = Delta(diff)                      # or Mapping
assert t1 + delta == t2                  # deepcopy unless mutate=True
assert delta.to_dict()                   # delta-shaped dict
assert extract({"a": [1, 2]}, "root['a'][1]") == 2
```

## Implementation

- Pure Python under `python/deepdiff_rust/` (`_path.py`, `_delta.py`).
- `DeepDiff._to_delta_dict(...)` reshapes our report into DeltaResult-like dict
  (strip `old_value` when directed; normalize `set_item_*` path lists →
  `{parent_path: {member, ...}}`).
- Apply order matches DeepDiff 9.1.0 for supported categories.
- `deserializer=` / `serializer=` callables supported (e.g. `json.loads` /
  `json.dumps`). Mapping `diff` ignores deserializer. str/bytes `diff` requires
  deserializer. Pickle default / file / flat still `NotImplementedError`.

## Out of scope

dump/loads, flat_dicts/rows, `view='delta'`, DeepHash/DeepSearch.
