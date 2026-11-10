//! The value normalization `DeepDiff` options apply before comparing and
//! hashing: `significant_digits` number strings and `ignore_string_case`.

use std::borrow::Cow;

use num_bigint::BigInt;
use num_traits::{FromPrimitive, ToPrimitive};

use crate::value::{Number, Str};

/// `number_to_string` (helper.py): `number` rounded to `digits` decimals,
/// formatted `{:.Nf}` or (`exponent`) `{:.Ne}` with the exponent's leading
/// zero stripped.
#[must_use]
pub(crate) fn number_to_string(number: &Number, digits: usize, exponent: bool) -> String {
    let mut x = if number.is_f64() {
        let f = number
            .as_f64()
            .expect("Number::is_f64 guarantees as_f64 succeeds");
        // Python's `round(f, digits)`: the correctly rounded decimal, read back.
        if f.is_finite() {
            format!("{f:.digits$}")
                .parse()
                .expect("a formatted float parses")
        } else {
            f
        }
    } else {
        // `round(int, digits)` keeps the int; formatting it converts to float.
        int_to_f64(number)
    };
    if x == 0.0 {
        x = 0.0;
    }
    if x.is_nan() {
        return "nan".to_owned();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf" } else { "-inf" }.to_owned();
    }
    if !exponent {
        return format!("{x:.digits$}");
    }
    let formatted = format!("{x:.digits$e}");
    let (mantissa, exp) = formatted
        .split_once('e')
        .expect("LowerExp always writes an exponent");
    if exp.starts_with('-') {
        formatted
    } else {
        format!("{mantissa}e+{exp}")
    }
}

/// `float(int)`: correctly rounded, infinite past `f64`'s range.
#[must_use]
pub(crate) fn int_to_f64(number: &Number) -> f64 {
    #[allow(
        clippy::cast_precision_loss,
        reason = "Python's float(int) rounds the same way"
    )]
    match number.as_i128() {
        Some(i) => i as f64,
        None => number
            .as_big()
            .and_then(ToPrimitive::to_f64)
            .unwrap_or(f64::INFINITY),
    }
}

/// Python `==` between two numbers; an int and a float compare exactly.
#[must_use]
pub(crate) fn numbers_python_equal(a: &Number, b: &Number) -> bool {
    match (a.is_f64(), b.is_f64()) {
        (true, false) => int_equals_float(b, as_float(a)),
        (false, true) => int_equals_float(a, as_float(b)),
        _ => crate::diff::numbers_equal(a, b),
    }
}

/// `number` as Python's `float(number)`.
#[must_use]
pub(crate) fn as_float(number: &Number) -> f64 {
    if number.is_f64() {
        number
            .as_f64()
            .expect("Number::is_f64 guarantees as_f64 succeeds")
    } else {
        int_to_f64(number)
    }
}

fn int_equals_float(int: &Number, float: f64) -> bool {
    let int = int.as_i128().map_or_else(
        || int.as_big().expect("an int beyond i128 is big").clone(),
        BigInt::from,
    );
    float.is_finite() && float.fract() == 0.0 && BigInt::from_f64(float) == Some(int)
}

/// `math.isclose(a, b, abs_tol=epsilon)` at its default `rel_tol=1e-09`.
#[must_use]
#[allow(clippy::float_cmp, reason = "isclose's own exact-equality shortcut")]
pub(crate) fn is_close(a: f64, b: f64, epsilon: f64) -> bool {
    if a == b {
        return true;
    }
    if a.is_infinite() || b.is_infinite() {
        return false;
    }
    let diff = (b - a).abs();
    diff <= (1e-9 * b).abs() || diff <= (1e-9 * a).abs() || diff <= epsilon
}

/// `logarithmic_distance` (distance.py).
#[must_use]
pub(crate) fn log_distance(a: f64, b: f64) -> f64 {
    let log = |x: f64| (x.abs() + 1e-10).ln().copysign(x);
    (log(a) - log(b)).abs()
}

/// `s` as `ignore_string_case` compares and hashes it: `str.lower()` when
/// `fold`; a string holding a lone surrogate is kept as is.
#[must_use]
pub(crate) fn fold_case(s: &Str, fold: bool) -> Cow<'_, [u8]> {
    match s.as_utf8() {
        Some(text) if fold => Cow::Owned(text.to_lowercase().into_bytes()),
        _ => Cow::Borrowed(s.as_bytes()),
    }
}

/// What `DeepHash` normalizes in a leaf before hashing it.
#[derive(Debug, Clone, Copy, Default)]
#[allow(
    clippy::struct_excessive_bools,
    reason = "one flag per DeepDiff option"
)]
pub(crate) struct HashNorm {
    pub(crate) significant_digits: Option<usize>,
    pub(crate) exponent_notation: bool,
    pub(crate) ignore_numeric_type_changes: bool,
    pub(crate) ignore_string_case: bool,
    pub(crate) use_enum_value: bool,
    pub(crate) report_repetition: bool,
}

impl HashNorm {
    pub(crate) fn of(opts: &crate::diff::DiffOptions) -> Self {
        Self {
            significant_digits: opts.significant_digits,
            exponent_notation: opts.exponent_notation,
            ignore_numeric_type_changes: opts.ignore_numeric_type_changes,
            ignore_string_case: opts.ignore_string_case,
            use_enum_value: opts.use_enum_value,
            report_repetition: opts.report_repetition,
        }
    }
}
