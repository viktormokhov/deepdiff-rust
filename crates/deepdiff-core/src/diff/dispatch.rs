//! The recursive traversal core: [`diff_at`]'s type-dispatch switch, the
//! depth-guard invariants it enforces on every step, and the shared
//! path-buffer helper ([`scoped`]) every container loop in `super::array`
//! and `super::object` uses to push/pop path segments as they recurse.
//! See `docs/design/depth-budget.md` for the depth-guard proof.

use crate::value::{Object, ObjectKind, Value, same_class};

use crate::error::Error;
use crate::ignore_order::IgnoreOrderMemo;
use crate::path::{PathSegment, render_path};
use crate::report::Report;

use super::{
    DiffOptions, array_diff, datetime_diff, effective_type_name, leaf_diff, numbers_match,
    numeric_diff, object_diff, scalar_diff, set_diff, type_change_report,
};

/// The recursive core of [`diff_with_max_depth()`](super::diff_with_max_depth): identical
/// dispatch, carrying the path and depth accumulated so far, so nested findings get their full
/// deep path and the recursion-depth bound can be enforced.
///
/// `path` is the one buffer shared across the traversal; its segments are pushed and popped by
/// [`scoped`].
pub(crate) fn diff_at(
    path: &mut Vec<PathSegment>,
    a: &Value,
    b: &Value,
    depth: usize,
    opts: &DiffOptions,
    memo: &IgnoreOrderMemo,
) -> Result<Report, Error> {
    check_traversal_depth(path, depth, opts.max_depth)?;

    match (a, b) {
        (Value::Null, Value::Null) => Ok(Report::new()),
        (Value::Bool(old), Value::Bool(new)) => {
            scalar_diff(path, old == new, a, b, depth, opts.max_depth)
        }
        (Value::Number(old), Value::Number(new)) => numeric_diff(path, old, new, a, b, depth, opts),
        (Value::Str(_), Value::Str(_)) if opts.ignore_string_case => {
            case_folded_diff(path, a, b, depth, opts.max_depth)
        }
        (Value::Str(old), Value::Str(new)) => {
            scalar_diff(path, old == new, a, b, depth, opts.max_depth)
        }
        (Value::DateTime(old), Value::DateTime(new)) => {
            if same_class(a, b) || opts.same_group(a, b) {
                datetime_diff(path, old.value(), new.value(), depth, opts.max_depth)
            } else {
                type_change_report(path, a, b, depth, opts.max_depth)
            }
        }
        (Value::Date(old), Value::Date(new)) => {
            if same_class(a, b) || opts.same_group(a, b) {
                scalar_diff(path, old == new, a, b, depth, opts.max_depth)
            } else {
                type_change_report(path, a, b, depth, opts.max_depth)
            }
        }
        (Value::Time(old), Value::Time(new)) => {
            if same_class(a, b) || opts.same_group(a, b) {
                // Plain `_diff_time` equality — no normalization step,
                // unlike `datetime_diff` (see `docs/design/value-model.md`).
                scalar_diff(
                    path,
                    crate::datetime::times_equal(old.value(), new.value()),
                    a,
                    b,
                    depth,
                    opts.max_depth,
                )
            } else {
                type_change_report(path, a, b, depth, opts.max_depth)
            }
        }
        (Value::TimeDelta(old), Value::TimeDelta(new)) => {
            if same_class(a, b) || opts.same_group(a, b) {
                scalar_diff(path, old == new, a, b, depth, opts.max_depth)
            } else {
                type_change_report(path, a, b, depth, opts.max_depth)
            }
        }
        (Value::Array(old), Value::Array(new)) | (Value::Tuple(old), Value::Tuple(new)) => {
            if same_class(a, b) || opts.same_group(a, b) {
                array_diff(path, old, new, depth, opts, memo)
            } else {
                type_change_report(path, a, b, depth, opts.max_depth)
            }
        }
        (Value::Set(old), Value::Set(new)) | (Value::FrozenSet(old), Value::FrozenSet(new)) => {
            if same_class(a, b) || opts.same_group(a, b) {
                set_diff(path, old, new, depth, opts, memo)
            } else {
                type_change_report(path, a, b, depth, opts.max_depth)
            }
        }
        (Value::Object(old), Value::Object(new))
            if old.kind() == ObjectKind::Dict && new.kind() == ObjectKind::Dict =>
        {
            if same_class(a, b) || opts.same_group(a, b) {
                object_diff(path, old, new, depth, opts, memo)
            } else {
                type_change_report(path, a, b, depth, opts.max_depth)
            }
        }
        (Value::Object(_), _) | (_, Value::Object(_)) => {
            object_pair_diff(path, a, b, depth, opts, memo)
        }
        (Value::Leaf(old), Value::Leaf(new)) if old.type_name() == new.type_name() => {
            if same_class(a, b) || opts.same_group(a, b) {
                leaf_diff(path, a, b, depth, opts)
            } else {
                type_change_report(path, a, b, depth, opts.max_depth)
            }
        }
        _ if opts.same_group(a, b) => grouped_diff(path, a, b, depth, opts, memo),
        _ => type_change_report(path, a, b, depth, opts.max_depth),
    }
}

/// [`diff_at`] for a pair with a custom object or token on either side, kept
/// off its frame: nothing for a pair [`IgnoreOrderMemo::skips`], a resolved
/// token's value through [`diff_at`] again, a finding carrying a failed
/// object's token where a walk meets it, else the object walk or a
/// `type_changes`.
#[inline(never)]
fn object_pair_diff(
    path: &mut Vec<PathSegment>,
    a: &Value,
    b: &Value,
    depth: usize,
    opts: &DiffOptions,
    memo: &IgnoreOrderMemo,
) -> Result<Report, Error> {
    if IgnoreOrderMemo::skips(a, b) {
        return Ok(Report::new());
    }
    let resolved_a = memo.resolve(a, b, false);
    let resolved_b = memo.resolve(b, resolved_a.as_deref().unwrap_or(a), false);
    if resolved_a.is_some() || resolved_b.is_some() {
        let a = resolved_a.as_deref().unwrap_or(a);
        let b = resolved_b.as_deref().unwrap_or(b);
        return diff_at(path, a, b, depth, opts, memo);
    }
    if opts.use_enum_value
        && !same_class(a, b)
        && let Some((a, b)) = enum_values(a, b)
    {
        if effective_type_name(a) == effective_type_name(b) {
            return diff_at(path, a, b, depth, opts, memo);
        }
        let equal = grouped_scalars_equal(a, b, opts);
        return scalar_diff(path, equal, a, b, depth, opts.max_depth);
    }
    match (a, b) {
        (Value::Object(old), Value::Object(new)) if same_class(a, b) => {
            match (old.failure_token(), new.failure_token()) {
                (None, None) => object_diff(path, old, new, depth, opts, memo),
                (old_token, new_token) => scalar_diff(
                    path,
                    false,
                    old_token.as_ref().unwrap_or(a),
                    new_token.as_ref().unwrap_or(b),
                    depth,
                    opts.max_depth,
                ),
            }
        }
        _ => type_change_report(path, a, b, depth, opts.max_depth),
    }
}
/// Deep structural equality, for the top-level equal-inputs fast path; delegates to [`Value`]'s
/// iterative [`PartialEq`] (`docs/design/value-model.md`).
#[must_use]
pub(crate) fn values_equal(a: &Value, b: &Value) -> bool {
    a == b
}
/// Returns `true` if `value`'s own nesting exceeds `limit`, with `value` as depth `0`. Iterative,
/// so it cannot overflow the stack it guards; peak heap tracks input size.
pub(crate) fn deeper_than(value: &Value, limit: usize) -> bool {
    let mut stack: Vec<(&Value, usize)> = vec![(value, 0)];

    while let Some((v, depth)) = stack.pop() {
        if depth > limit {
            return true;
        }
        match v {
            Value::Array(items) | Value::Tuple(items) => {
                stack.extend(items.iter().map(|item| (item, depth + 1)));
            }
            Value::Set(items) | Value::FrozenSet(items) => {
                stack.extend(items.iter().map(|item| (item, depth + 1)));
            }
            Value::Object(map) => stack.extend(map.values().map(|item| (item, depth + 1))),
            Value::Null
            | Value::Bool(_)
            | Value::Number(_)
            | Value::Str(_)
            | Value::DateTime(_)
            | Value::Date(_)
            | Value::Time(_)
            | Value::TimeDelta(_)
            | Value::Leaf(_) => {}
        }
    }

    false
}
/// Rejects `value` (see [`deeper_than`]) if its nesting exceeds the budget remaining at `depth`
/// (`max_depth.saturating_sub(depth)`), not a flat `max_depth`.
pub(crate) fn check_value_depth(
    path: &[PathSegment],
    value: &Value,
    depth: usize,
    max_depth: usize,
) -> Result<(), Error> {
    if deeper_than(value, max_depth.saturating_sub(depth)) {
        return Err(Error::MaxDepthExceeded {
            path: render_path(path).to_string(),
            max_depth,
        });
    }
    Ok(())
}
/// Like [`deeper_than`], but walks a dict's fields directly. `limit` is the caller's already
/// reduced remaining budget.
pub(crate) fn map_deeper_than(map: &Object, limit: usize) -> bool {
    if limit == 0 {
        !map.is_empty()
    } else {
        map.values().any(|value| deeper_than(value, limit - 1))
    }
}
/// [`check_value_depth`] for a dict not yet cloned into a `Value`, so the check precedes the clone.
pub(crate) fn check_map_depth(
    path: &[PathSegment],
    map: &Object,
    depth: usize,
    max_depth: usize,
) -> Result<(), Error> {
    if map_deeper_than(map, max_depth.saturating_sub(depth)) {
        return Err(Error::MaxDepthExceeded {
            path: render_path(path).to_string(),
            max_depth,
        });
    }
    Ok(())
}
/// Rejects if the path depth itself (`depth`) exceeds `max_depth`; [`check_value_depth`] enforces
/// the other half of the shared budget.
pub(crate) fn check_traversal_depth(
    path: &[PathSegment],
    depth: usize,
    max_depth: usize,
) -> Result<(), Error> {
    if depth > max_depth {
        return Err(Error::MaxDepthExceeded {
            path: render_path(path).to_string(),
            max_depth,
        });
    }
    Ok(())
}
/// Pushes `seg`, runs `f`, then pops it again, even on failure; `path.len()` is what every depth
/// check measures against the shared budget.
pub(crate) fn scoped<T>(
    path: &mut Vec<PathSegment>,
    seg: PathSegment,
    f: impl FnOnce(&mut Vec<PathSegment>) -> T,
) -> T {
    path.push(seg);
    let result = f(path);
    path.pop();
    result
}

/// A pair of different types sharing an `ignore_type_in_groups` group,
/// compared as `DeepDiff._diff` goes on once it skips `type_changes`.
#[inline(never)]
fn grouped_diff(
    path: &mut Vec<PathSegment>,
    a: &Value,
    b: &Value,
    depth: usize,
    opts: &DiffOptions,
    memo: &IgnoreOrderMemo,
) -> Result<Report, Error> {
    match (a, b) {
        (Value::Array(old) | Value::Tuple(old), Value::Array(new) | Value::Tuple(new)) => {
            array_diff(path, old, new, depth, opts, memo)
        }
        (Value::Set(old) | Value::FrozenSet(old), Value::Set(new) | Value::FrozenSet(new)) => {
            set_diff(path, old, new, depth, opts, memo)
        }
        _ => {
            let equal = grouped_scalars_equal(a, b, opts);
            scalar_diff(path, equal, a, b, depth, opts.max_depth)
        }
    }
}

/// `_diff_str` under `ignore_string_case`: both strings lowered before
/// comparing and reporting them. Off [`diff_at`]'s frame, which bounds `max_depth`.
#[inline(never)]
fn case_folded_diff(
    path: &[PathSegment],
    a: &Value,
    b: &Value,
    depth: usize,
    max_depth: usize,
) -> Result<Report, Error> {
    let (a, b) = (lowered(a), lowered(b));
    scalar_diff(path, a == b, &a, &b, depth, max_depth)
}

/// A string `str.lower()`ed; one holding a lone surrogate is kept as is.
fn lowered(value: &Value) -> Value {
    match value {
        Value::Str(s) => match s.as_utf8() {
            Some(text) => Value::Str(crate::value::Str::Utf8(text.to_lowercase().into())),
            None => value.clone(),
        },
        _ => value.clone(),
    }
}

/// Python `==` for two scalars of different types in one type group: numbers
/// under the numeric options, `str` against ASCII `bytes` as `_diff_str`
/// decodes them, `str` against a `UUID` under `ignore_uuid_types`.
fn grouped_scalars_equal(a: &Value, b: &Value, opts: &DiffOptions) -> bool {
    use crate::leaf::{Leaf, parse_uuid};
    if opts.rounds_numbers()
        && let (Some(x), Some(y)) = (as_number(a), as_number(b))
    {
        return numbers_match(&x, &y, opts);
    }
    // A rounded `complex` is a `complex` string no real number's matches.
    let complex = |v: &Value| matches!(v, Value::Leaf(l) if matches!(&***l, Leaf::Complex(..)));
    if opts.rounds_numbers() && (complex(a) || complex(b)) {
        return false;
    }
    match (a, b) {
        (Value::Null, _) | (_, Value::Null) => false,
        (Value::Str(s), Value::Leaf(leaf)) | (Value::Leaf(leaf), Value::Str(s)) => match &***leaf {
            Leaf::Bytes(bytes) => {
                let fold = |b: &[u8]| {
                    if opts.ignore_string_case {
                        b.to_ascii_lowercase()
                    } else {
                        b.to_vec()
                    }
                };
                bytes.is_ascii() && fold(bytes) == fold(s.as_bytes())
            }
            Leaf::Uuid(u) => s.as_utf8().and_then(parse_uuid) == Some(*u),
            _ => false,
        },
        _ => {
            let key = crate::lcs::python_scalar_key;
            key(a).is_some_and(|old| Some(old) == key(b))
        }
    }
}

/// `value` as a [`Number`] the numeric options round: an int, a float, or a
/// `Decimal` by its nearest `f64`.
fn as_number(value: &Value) -> Option<crate::value::Number> {
    use crate::leaf::Leaf;
    use crate::value::Number;
    match value {
        Value::Number(n) => Some(n.clone()),
        Value::Leaf(leaf) => match &***leaf {
            Leaf::Decimal(d) => Some(Number::from_f64(d.approx())),
            _ => None,
        },
        _ => None,
    }
}

/// `use_enum_value`'s pair: each `Enum` member replaced by its `value`, `None` with no member.
fn enum_values<'a>(a: &'a Value, b: &'a Value) -> Option<(&'a Value, &'a Value)> {
    let value = |v: &'a Value| match v {
        Value::Object(o) => o.enum_value(),
        _ => None,
    };
    match (value(a), value(b)) {
        (None, None) => None,
        (x, y) => Some((x.unwrap_or(a), y.unwrap_or(b))),
    }
}
