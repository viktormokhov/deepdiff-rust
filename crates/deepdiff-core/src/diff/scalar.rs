//! Leaf-level (non-container) comparison: scalar/numeric equality and the
//! `values_changed`/`type_changes` finding builders that `super::dispatch`'s
//! [`super::diff_at`] dispatches to whenever a pair is not two dicts or two
//! arrays.

use crate::datetime::DateTime;
use crate::leaf::Leaf;
use crate::value::{Number, Typed, Value, class_name};

use crate::error::Error;
use crate::path::{PathSegment, render_path};
use crate::report::{Report, TypeChangeEntry, ValuesChangedEntry};

use super::{DiffOptions, check_value_depth};

/// The base-type name for `value`, ignoring any subclass name ([`effective_type_name`] has that).
/// A number is `"float"` when its literal has a decimal point or exponent, else `"int"`.
pub(crate) fn python_type_name(value: &Value) -> &'static str {
    match value {
        Value::Null => "NoneType",
        Value::Bool(_) => "bool",
        Value::Number(n) if n.is_f64() => "float",
        Value::Number(_) => "int",
        Value::Str(_) => "str",
        Value::DateTime(_) => "datetime",
        Value::Date(_) => "date",
        Value::Time(_) => "time",
        Value::TimeDelta(_) => "timedelta",
        Value::Array(_) => "list",
        Value::Tuple(_) => "tuple",
        Value::Set(_) => "set",
        Value::FrozenSet(_) => "frozenset",
        Value::Object(_) => "dict",
        Value::Leaf(leaf) => leaf.type_name(),
    }
}

/// [`python_type_name`], overridden by [`class_name`] when `value` carries a
/// subclass name — the name `DeepDiff` actually reports for `old_type`/
/// `new_type` (`type(obj).__name__`, not the base type it structurally
/// compares as). See [`crate::value::Typed`]'s doc.
pub(crate) fn effective_type_name(value: &Value) -> String {
    class_name(value).map_or_else(|| python_type_name(value).to_string(), str::to_string)
}
/// Builds a single-entry `type_changes` report at `path`, depth-checking both values before
/// cloning either.
pub(crate) fn type_change_report(
    path: &[PathSegment],
    a: &Value,
    b: &Value,
    depth: usize,
    max_depth: usize,
) -> Result<Report, Error> {
    check_value_depth(path, a, depth, max_depth)?;
    check_value_depth(path, b, depth, max_depth)?;

    let mut report = Report::new();
    report.insert_type_change(
        path.to_vec(),
        TypeChangeEntry {
            old_type: effective_type_name(a),
            new_type: effective_type_name(b),
            old_value: a.clone(),
            new_value: b.clone(),
            new_path: None,
        },
    );
    Ok(report)
}
/// Builds an empty report when `equal`, else a single-entry `values_changed` report at `path`,
/// depth-checking both values before cloning either.
pub(crate) fn scalar_diff(
    path: &[PathSegment],
    equal: bool,
    a: &Value,
    b: &Value,
    depth: usize,
    max_depth: usize,
) -> Result<Report, Error> {
    if equal {
        return Ok(Report::new());
    }
    check_value_depth(path, a, depth, max_depth)?;
    check_value_depth(path, b, depth, max_depth)?;

    let mut report = Report::new();
    report.insert_values_changed(
        path.to_vec(),
        ValuesChangedEntry {
            diff: crate::unified_diff::str_diff_field(a, b),
            old_value: a.clone(),
            new_value: b.clone(),
            new_path: None,
        },
    );
    Ok(report)
}
/// Diffs two datetimes, which `DeepDiff` compares by *instant* after
/// normalizing each to UTC (`_diff_datetime` -> `datetime_normalize`, with a
/// naive value stamped as UTC rather than read in local time).
///
/// A `values_changed` entry carries the pair as UTC: `10:00-05:00` is reported as `15:00+00:00`.
pub(crate) fn datetime_diff(
    path: &[PathSegment],
    old: DateTime,
    new: DateTime,
    depth: usize,
    max_depth: usize,
) -> Result<Report, Error> {
    let (old, new) = normalized_pair(path, old, new)?;

    scalar_diff(
        path,
        old == new,
        &Value::DateTime(old.into()),
        &Value::DateTime(new.into()),
        depth,
        max_depth,
    )
}
/// Normalizes both sides of a datetime comparison to UTC, or reports
/// [`Error::DateTimeOutOfRange`] at `path` when one of them has no
/// normalized form; see `tests/golden/README.md`, "Datetime outside year `1..=9999`".
///
/// # Errors
///
/// Returns [`Error::DateTimeOutOfRange`] if either value's UTC wall clock
/// leaves the `1..=9999` year range.
pub(crate) fn normalized_pair(
    path: &[PathSegment],
    old: DateTime,
    new: DateTime,
) -> Result<(DateTime, DateTime), Error> {
    let out_of_range = || Error::DateTimeOutOfRange {
        path: render_path(path).to_string(),
    };

    Ok((
        old.to_utc().ok_or_else(out_of_range)?,
        new.to_utc().ok_or_else(out_of_range)?,
    ))
}
/// Diffs two same-JSON-variant numbers, first checking whether one is an int
/// and the other a float (a `type_changes` finding, regardless of numeric
/// value), then comparing numerically within the same type via
/// [`numbers_equal`].
pub(crate) fn numeric_diff(
    path: &[PathSegment],
    old: &Number,
    new: &Number,
    a: &Value,
    b: &Value,
    depth: usize,
    opts: &DiffOptions,
) -> Result<Report, Error> {
    if old.is_f64() != new.is_f64() && !opts.same_group(a, b) {
        return type_change_report(path, a, b, depth, opts.max_depth);
    }
    let equal = numbers_match(old, new, opts);
    scalar_diff(path, equal, a, b, depth, opts.max_depth)
}
/// `_diff_numbers`'s equality under the numeric options, after
/// `ignore_nan_inequality`'s `nan` shortcut.
#[inline(never)]
pub(crate) fn numbers_match(old: &Number, new: &Number, opts: &DiffOptions) -> bool {
    use crate::normalize::{as_float, is_close, log_distance, number_to_string};
    let (x, y) = (as_float(old), as_float(new));
    if opts.ignore_nan_inequality && old.is_f64() && x.is_nan() && new.is_f64() && y.is_nan() {
        return true;
    }
    if let Some(threshold) = opts.log_scale_threshold {
        return log_distance(x, y) < threshold;
    }
    if let Some(epsilon) = opts.math_epsilon {
        return is_close(x, y, epsilon);
    }
    match opts.significant_digits {
        Some(digits) => {
            let e = opts.exponent_notation;
            number_to_string(old, digits, e) == number_to_string(new, digits, e)
        }
        None => crate::normalize::numbers_python_equal(old, new),
    }
}
/// Numeric equality shared by [`numeric_diff`] and [`values_equal`](super::values_equal): an int
/// and a float are never equal, floats compare by IEEE-754 `==`, ints by value across
/// representations ([`Number::integer_cmp`]).
pub(crate) fn numbers_equal(old: &Number, new: &Number) -> bool {
    if old.is_f64() != new.is_f64() {
        return false;
    }

    if old.is_f64() {
        let old_f = old
            .as_f64()
            .expect("Number::is_f64 guarantees as_f64 succeeds");
        let new_f = new
            .as_f64()
            .expect("Number::is_f64 guarantees as_f64 succeeds");
        floats_equal(old_f, new_f)
    } else {
        old.integer_cmp(new).is_eq()
    }
}
fn floats_equal(a: f64, b: f64) -> bool {
    #[allow(
        clippy::float_cmp,
        reason = "exact IEEE-754 equality is the intended rule (Python == semantics, including 0.0 == -0.0 and NaN != NaN)"
    )]
    {
        a == b
    }
}
/// `_diff_str`, `_diff_numbers` or `_diff_uuids` for two [`Leaf`]s of one
/// kind. Off [`super::diff_at`]'s frame, which bounds `max_depth`.
///
/// ponytail: a `Decimal` or `complex` rounds through `f64` under the numeric
/// options, so digits past ~15 are lost there; port `Decimal.quantize` if
/// that matters.
#[inline(never)]
pub(crate) fn leaf_diff(
    path: &[PathSegment],
    a: &Value,
    b: &Value,
    depth: usize,
    opts: &DiffOptions,
) -> Result<Report, Error> {
    let (Value::Leaf(old), Value::Leaf(new)) = (a, b) else {
        unreachable!("leaf_diff is only called on two leaves");
    };
    let float = Number::from_f64;
    let rounds = opts.rounds_numbers();
    let equal = match (&***old, &***new) {
        (Leaf::Bytes(_), Leaf::Bytes(_)) if opts.ignore_string_case => {
            let (a, b) = (lowered_bytes(a), lowered_bytes(b));
            return scalar_diff(path, a == b, &a, &b, depth, opts.max_depth);
        }
        (Leaf::Decimal(x), Leaf::Decimal(y)) if rounds => {
            numbers_match(&float(x.approx()), &float(y.approx()), opts)
        }
        (Leaf::Complex(xr, xi), Leaf::Complex(yr, yi)) if rounds => {
            numbers_match(&float(*xr), &float(*yr), opts)
                && numbers_match(&float(*xi), &float(*yi), opts)
        }
        (x, y) => x == y,
    };
    scalar_diff(path, equal, a, b, depth, opts.max_depth)
}

/// A `bytes` leaf `bytes.lower()`ed, keeping its class name.
fn lowered_bytes(value: &Value) -> Value {
    match value {
        Value::Leaf(leaf) => match &***leaf {
            Leaf::Bytes(b) => Value::Leaf(Typed::with_class_name(
                Box::new(Leaf::Bytes(b.to_ascii_lowercase().into())),
                leaf.class_name().map(Into::into),
            )),
            _ => value.clone(),
        },
        _ => value.clone(),
    }
}
