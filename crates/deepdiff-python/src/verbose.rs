//! `DeepDiff`'s `verbose_level` 0 and 1, derived from the level-2 report the
//! core renders (`deepdiff.model.TextResult`).

use deepdiff_core::Value;
use deepdiff_core::value::{Builder, ObjectKey};

/// Categories that report bare paths below `verbose_level=2`.
const PATHS_ONLY: [&str; 4] = [
    "dictionary_item_added",
    "dictionary_item_removed",
    "attribute_added",
    "attribute_removed",
];

/// `report` (rendered at level 2) as `DeepDiff` renders it at `level` 0 or 1.
pub(crate) fn at_verbose_level(report: &Value, level: u8) -> Value {
    let Value::Object(categories) = report else {
        return report.clone();
    };
    let dropped: &[&str] = if level == 0 {
        &["new_path", "old_value", "new_value"]
    } else {
        &["new_path"]
    };
    let mut builder = Builder::new();
    let mut out = Vec::new();
    for (key, value) in categories.iter() {
        let name = key.as_str().unwrap_or_default();
        let rendered = match (name, value) {
            ("values_changed", _) if level == 0 => continue,
            (_, Value::Object(entries)) if PATHS_ONLY.contains(&name) => Value::Array(
                entries
                    .keys()
                    .map(key_value)
                    .collect::<Vec<_>>()
                    .into_boxed_slice()
                    .into(),
            ),
            ("type_changes" | "values_changed", Value::Object(entries)) => {
                let rows = entries
                    .iter()
                    .map(|(path, entry)| (path.clone(), without(entry, dropped, &mut builder)))
                    .collect();
                builder.object_with_keys(rows)
            }
            _ => value.clone(),
        };
        out.push((key.clone(), rendered));
    }
    builder.object_with_keys(out)
}

fn key_value(key: &ObjectKey) -> Value {
    match key {
        ObjectKey::Str(key) => Value::Str(key.into()),
        ObjectKey::Other(value) => (**value).clone(),
    }
}

/// `entry` without the fields named in `dropped`.
fn without(entry: &Value, dropped: &[&str], builder: &mut Builder) -> Value {
    let Value::Object(fields) = entry else {
        return entry.clone();
    };
    let kept = fields
        .iter()
        .filter(|(key, _)| !key.as_str().is_some_and(|key| dropped.contains(&key)))
        .map(|(key, value)| (key.clone(), value.clone()))
        .collect();
    builder.object_with_keys(kept)
}
