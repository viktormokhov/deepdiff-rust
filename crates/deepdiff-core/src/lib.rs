//! Python-independent structural diff primitives.
//!
//! This crate intentionally starts with a small JSON-compatible value model.
//! Python-native values and identity-sensitive objects belong in the PyO3
//! adapter and must not be lossy-converted to JSON.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// A deterministic, owned value representation for the initial core.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Value {
    Null,
    Bool(bool),
    Number(serde_json::Number),
    String(String),
    Array(Vec<Value>),
    Object(BTreeMap<String, Value>),
}

/// A single structural change.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Change {
    /// JSONPath-like path, rooted at `root`.
    pub path: String,
    pub kind: ChangeKind,
}

/// Supported change categories.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ChangeKind {
    TypeChanged,
    ValueChanged,
    Added,
    Removed,
}

/// Compare two values recursively and return deterministic changes.
///
/// This first implementation is deliberately limited to JSON-compatible
/// values. It is a foundation for the richer Python object model.
pub fn diff(old: &Value, new: &Value) -> Vec<Change> {
    let mut changes = Vec::new();
    compare(old, new, "root", &mut changes);
    changes
}

fn compare(old: &Value, new: &Value, path: &str, out: &mut Vec<Change>) {
    match (old, new) {
        (Value::Null, Value::Null) => {}
        (Value::Bool(a), Value::Bool(b)) if a == b => {}
        (Value::Number(a), Value::Number(b)) if a == b => {}
        (Value::String(a), Value::String(b)) if a == b => {}
        (Value::Array(a), Value::Array(b)) => {
            let common = a.len().min(b.len());
            for index in 0..common {
                compare(&a[index], &b[index], &format!("{path}[{index}]"), out);
            }
            for index in common..a.len() {
                out.push(Change {
                    path: format!("{path}[{index}]"),
                    kind: ChangeKind::Removed,
                });
            }
            for index in common..b.len() {
                out.push(Change {
                    path: format!("{path}[{index}]"),
                    kind: ChangeKind::Added,
                });
            }
        }
        (Value::Object(a), Value::Object(b)) => {
            for (key, old_value) in a {
                match b.get(key) {
                    Some(new_value) => {
                        compare(old_value, new_value, &format!("{path}['{key}']"), out);
                    }
                    None => out.push(Change {
                        path: format!("{path}['{key}']"),
                        kind: ChangeKind::Removed,
                    }),
                }
            }
            for key in b.keys().filter(|key| !a.contains_key(*key)) {
                out.push(Change {
                    path: format!("{path}['{key}']"),
                    kind: ChangeKind::Added,
                });
            }
        }
        (Value::Null, _)
        | (Value::Bool(_), Value::Number(_) | Value::String(_) | Value::Array(_) | Value::Object(_))
        | (Value::Number(_), Value::Bool(_) | Value::String(_) | Value::Array(_) | Value::Object(_))
        | (Value::String(_), Value::Bool(_) | Value::Number(_) | Value::Array(_) | Value::Object(_))
        | (Value::Array(_), Value::Bool(_) | Value::Number(_) | Value::String(_) | Value::Object(_))
        | (Value::Object(_), Value::Bool(_) | Value::Number(_) | Value::String(_) | Value::Array(_))
        | (_, Value::Null) => out.push(Change {
            path: path.to_owned(),
            kind: ChangeKind::TypeChanged,
        }),
        (Value::Bool(_), Value::Bool(_))
        | (Value::Number(_), Value::Number(_))
        | (Value::String(_), Value::String(_)) => out.push(Change {
            path: path.to_owned(),
            kind: ChangeKind::ValueChanged,
        }),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_nested_value_change_and_added_key() {
        let old: Value = serde_json::from_str(r#"{"user":{"age":30},"active":true}"#).unwrap();
        let new: Value = serde_json::from_str(r#"{"user":{"age":31},"active":true,"role":"admin"}"#).unwrap();

        let changes = diff(&old, &new);
        assert!(changes.iter().any(|c| c.path == "root['user']['age']" && c.kind == ChangeKind::ValueChanged));
        assert!(changes.iter().any(|c| c.path == "root['role']" && c.kind == ChangeKind::Added));
    }

    #[test]
    fn equal_values_have_no_changes() {
        let value: Value = serde_json::from_str(r#"{"a":[1,2,3]}"#).unwrap();
        assert!(diff(&value, &value).is_empty());
    }
}
