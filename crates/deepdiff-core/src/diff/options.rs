//! The public API surface: [`DiffOptions`], [`DEFAULT_MAX_DEPTH`], and the
//! four entry points ([`diff()`], [`diff_with_options()`],
//! [`diff_with_max_depth()`], [`diff_with_resolver()`]) — all thin wrappers
//! around `super::dispatch`'s recursive [`super::diff_at`], differing in how
//! much of [`DiffOptions`] the caller controls and whether tokens resolve.

use std::collections::HashMap;
use std::sync::Arc;

use crate::value::Value;

use crate::error::Error;
use crate::report::Report;

use super::{diff_at, values_equal};

/// Default recursion-depth bound for [`diff()`]; it caps unequal nesting.
/// See `docs/design/depth-budget.md`, "Depth and value budget".
pub const DEFAULT_MAX_DEPTH: usize = 512;
/// The options a [`diff_with_options`] call runs with; `Default` matches
/// [`diff()`]: [`DEFAULT_MAX_DEPTH`], ordered comparison.
#[allow(
    clippy::struct_excessive_bools,
    reason = "one flag per DeepDiff keyword"
)]
#[derive(Debug, Clone, PartialEq)]
pub struct DiffOptions {
    /// The recursion-depth bound, independent of `ignore_order`; see
    /// `docs/design/depth-budget.md`.
    pub max_depth: usize,
    /// Mirrors `DeepDiff(..., ignore_order=True)`: lists and tuples at any
    /// depth pair by hash instead of by index; dicts are unaffected. See
    /// `docs/design/ignore-order.md`.
    pub ignore_order: bool,
    /// `significant_digits`: numbers compare by their rounded string.
    pub significant_digits: Option<usize>,
    /// `number_format_notation='e'` for [`Self::significant_digits`].
    pub exponent_notation: bool,
    /// `math_epsilon`: numbers compare by `math.isclose(abs_tol=...)`.
    pub math_epsilon: Option<f64>,
    /// `use_log_scale`'s `log_scale_similarity_threshold`, when on.
    pub log_scale_threshold: Option<f64>,
    pub ignore_nan_inequality: bool,
    pub ignore_string_case: bool,
    /// `ignore_numeric_type_changes`: numbers hash without their type.
    pub ignore_numeric_type_changes: bool,
    /// `ignore_type_in_groups`: each class name's bitmask of the groups it
    /// is in; values sharing a bit never report `type_changes`.
    pub type_groups: Option<Arc<HashMap<Box<str>, u64>>>,
    /// `use_enum_value`: an `Enum` member compares as its `value` against anything else.
    pub use_enum_value: bool,
    pub threshold_to_diff_deeper: f64,
    pub cutoff_distance_for_pairs: f64,
    pub cutoff_intersection_for_pairs: f64,
    pub zip_ordered_iterables: bool,
    /// `get_deep_distance`: the adapter reports [`Report::deep_distance`](crate::Report::deep_distance).
    pub get_deep_distance: bool,
    /// `report_repetition`: under `ignore_order`, count repeats and report `repetition_change`.
    pub report_repetition: bool,
}

impl Default for DiffOptions {
    fn default() -> Self {
        Self {
            max_depth: DEFAULT_MAX_DEPTH,
            ignore_order: false,
            significant_digits: None,
            exponent_notation: false,
            math_epsilon: None,
            log_scale_threshold: None,
            ignore_nan_inequality: false,
            ignore_string_case: false,
            ignore_numeric_type_changes: false,
            type_groups: None,
            use_enum_value: false,
            threshold_to_diff_deeper: crate::ignore_order::THRESHOLD_TO_DIFF_DEEPER,
            cutoff_distance_for_pairs: crate::ignore_order::CUTOFF_DISTANCE_FOR_PAIRS,
            cutoff_intersection_for_pairs: crate::ignore_order::CUTOFF_INTERSECTION_FOR_PAIRS,
            zip_ordered_iterables: false,
            get_deep_distance: false,
            report_repetition: false,
        }
    }
}
impl DiffOptions {
    /// Whether `a` and `b` share an `ignore_type_in_groups` group.
    pub(crate) fn same_group(&self, a: &Value, b: &Value) -> bool {
        self.type_groups.as_ref().is_some_and(|groups| {
            let mask = |v: &Value| {
                let name = super::effective_type_name(v);
                groups.get(name.as_str()).copied().unwrap_or(0)
            };
            mask(a) & mask(b) != 0
        })
    }

    /// Whether `significant_digits`, `math_epsilon` or `use_log_scale` rounds numbers.
    pub(crate) fn rounds_numbers(&self) -> bool {
        self.significant_digits.is_some()
            || self.math_epsilon.is_some()
            || self.log_scale_threshold.is_some()
    }

    /// Whether a pair the plain rules call unequal may still compare equal.
    pub(crate) fn normalizes(&self) -> bool {
        self.significant_digits.is_some()
            || self.math_epsilon.is_some()
            || self.log_scale_threshold.is_some()
            || self.ignore_nan_inequality
            || self.ignore_string_case
            || self.type_groups.is_some()
            || self.use_enum_value
    }
}

/// Diffs two JSON-shaped values into a [`Report`], bounding recursion at
/// [`DEFAULT_MAX_DEPTH`].
///
/// # Errors
///
/// Same as [`diff_with_max_depth`] at [`DEFAULT_MAX_DEPTH`].
///
/// # Examples
///
/// ```
/// use deepdiff_core::Value;
/// use deepdiff_core::diff::diff;
/// use serde_json::json;
///
/// let report = diff(&Value::from(json!(1)), &Value::from(json!(2))).unwrap();
/// assert!(!report.is_empty());
/// assert_eq!(
///     report.to_json_value(),
///     json!({"values_changed": {"root": {"new_value": 2, "old_value": 1}}})
/// );
/// ```
pub fn diff(a: &Value, b: &Value) -> Result<Report, Error> {
    diff_with_max_depth(a, b, DEFAULT_MAX_DEPTH)
}
/// Diffs two JSON-shaped values with a caller-chosen [`DiffOptions`]; see
/// `crate::ignore_order` when `opts.ignore_order` is `true`.
///
/// # Errors
///
/// Same as [`diff_with_max_depth`] at `opts.max_depth`.
///
/// # Examples
///
/// ```
/// use deepdiff_core::Value;
/// use deepdiff_core::diff::{DiffOptions, diff_with_options};
/// use serde_json::json;
///
/// let opts = DiffOptions {
///     ignore_order: true,
///     ..DiffOptions::default()
/// };
/// let report =
///     diff_with_options(&Value::from(json!([1, 2, 3])), &Value::from(json!([3, 2, 1])), &opts)
///         .unwrap();
/// assert!(report.is_empty());
/// ```
pub fn diff_with_options(a: &Value, b: &Value, opts: &DiffOptions) -> Result<Report, Error> {
    // A fresh memo per call: no state survives across diffs.
    diff_with_options_memo(
        a,
        b,
        opts,
        &crate::ignore_order::IgnoreOrderMemo::new().normalized(opts),
    )
}

/// A value compared in place of a token: shared, or borrowed from a value
/// that outlives the diff.
#[derive(Clone)]
pub enum Resolution<'r> {
    /// A value the caller converted for the token.
    Shared(std::sync::Arc<Value>),
    /// A value the caller already holds, such as the object a cycle token
    /// points back at.
    Borrowed(&'r Value),
}

impl std::ops::Deref for Resolution<'_> {
    type Target = Value;

    fn deref(&self) -> &Value {
        match self {
            Resolution::Shared(value) => value,
            Resolution::Borrowed(value) => value,
        }
    }
}

/// What the diff calls with a token's identity the first time it compares the
/// token with anything but itself; `None` leaves the token as it is.
pub type Resolver<'r> = dyn FnMut(&str) -> Option<Resolution<'r>> + Send + 'r;

/// [`diff_with_options`], comparing each token `resolver` resolves as its
/// value. A cycle token is compared that way only against an object of the
/// class it points back at, and otherwise stays a token.
///
/// # Errors
///
/// Same as [`diff_with_options`].
pub fn diff_with_resolver<'r>(
    a: &Value,
    b: &Value,
    opts: &DiffOptions,
    resolver: &'r mut Resolver<'r>,
) -> Result<Report, Error> {
    let mut report = diff_with_resolver_unmerged(a, b, opts, resolver)?;
    report.finish(opts);
    Ok(report)
}

/// [`diff_with_resolver`] before [`Report::finish`], so a caller can filter it and measure
/// [`Report::deep_distance`] first, in `DeepDiff`'s order.
///
/// # Errors
///
/// Same as [`diff_with_options`].
pub fn diff_with_resolver_unmerged<'r>(
    a: &Value,
    b: &Value,
    opts: &DiffOptions,
    resolver: &'r mut Resolver<'r>,
) -> Result<Report, Error> {
    let memo = crate::ignore_order::IgnoreOrderMemo::with_resolver(resolver).normalized(opts);
    diff_unmerged(a, b, opts, &memo)
}

/// The body of [`diff_with_options`], taking an explicit
/// [`crate::ignore_order::IgnoreOrderMemo`].
pub(crate) fn diff_with_options_memo(
    a: &Value,
    b: &Value,
    opts: &DiffOptions,
    memo: &crate::ignore_order::IgnoreOrderMemo,
) -> Result<Report, Error> {
    let mut report = diff_unmerged(a, b, opts, memo)?;
    report.finish(opts);
    Ok(report)
}

/// [`diff_with_options_memo`] before [`Report::finish`].
fn diff_unmerged(
    a: &Value,
    b: &Value,
    opts: &DiffOptions,
    memo: &crate::ignore_order::IgnoreOrderMemo,
) -> Result<Report, Error> {
    if values_equal(a, b) {
        return Ok(Report::new());
    }
    diff_at(&mut Vec::new(), a, b, 0, opts, memo)
}
/// Diffs like [`diff()`] with a caller-chosen recursion-depth bound; path
/// depth plus finding-value depth share it. See `docs/design/depth-budget.md`,
/// "Depth and value budget".
///
/// # Errors
///
/// [`Error::MaxDepthExceeded`] when the bound is exceeded;
/// [`Error::DateTimeOutOfRange`] for compared datetimes with no UTC form.
///
/// # Examples
///
/// ```
/// use deepdiff_core::Value;
/// use deepdiff_core::diff::diff_with_max_depth;
/// use serde_json::json;
///
/// // A tiny bound is enough for a shallow diff.
/// let report =
///     diff_with_max_depth(&Value::from(json!({"a": 1})), &Value::from(json!({"a": 2})), 3).unwrap();
/// assert!(!report.is_empty());
///
/// // Equal inputs never hit the bound, no matter how deep.
/// let deep = Value::from(json!({"a": {"b": {"c": {"d": {"e": 1}}}}}));
/// let report = diff_with_max_depth(&deep, &deep, 1).unwrap();
/// assert!(report.is_empty());
/// ```
pub fn diff_with_max_depth(a: &Value, b: &Value, max_depth: usize) -> Result<Report, Error> {
    diff_with_options(
        a,
        b,
        &DiffOptions {
            max_depth,
            ignore_order: false,
            ..DiffOptions::default()
        },
    )
}
