//! Python scalars with no arm of their own in [`crate::Value`]: `bytes`,
//! `decimal.Decimal`, `uuid.UUID` and `complex`.

use num_bigint::BigInt;

use crate::path::complex_repr;

/// One [`crate::Value::Leaf`] payload.
#[derive(Debug, Clone)]
pub enum Leaf {
    /// A Python `bytes`.
    Bytes(Box<[u8]>),
    /// A Python `decimal.Decimal` — see [`Decimal`].
    Decimal(Box<Decimal>),
    /// A Python `uuid.UUID`, by its `.int`.
    Uuid(u128),
    /// A Python `complex`: real and imaginary parts.
    Complex(f64, f64),
}

/// A `Decimal` by its `str()`, which rebuilds it exactly, plus the canonical
/// value key equality uses (`None` for a `NaN`) and its nearest `f64`.
#[derive(Debug, Clone)]
pub struct Decimal {
    text: Box<str>,
    key: Option<Box<str>>,
    approx: f64,
}

impl Decimal {
    /// Reads a `Decimal`'s `str()`.
    #[must_use]
    pub fn new(text: &str) -> Self {
        Self {
            key: decimal_key(text),
            approx: text.parse().unwrap_or(f64::NAN),
            text: text.into(),
        }
    }

    /// The `str()` this was read from.
    #[must_use]
    pub fn text(&self) -> &str {
        &self.text
    }

    /// The nearest `f64`, which the numeric options round.
    #[must_use]
    pub fn approx(&self) -> f64 {
        self.approx
    }

    /// `sign digits e exponent` with no leading or trailing zero digit, so
    /// Python-equal decimals share it; `None` for a `NaN`.
    pub(crate) fn key(&self) -> Option<&str> {
        self.key.as_deref()
    }
}

/// [`Decimal::key`] for decimal text in `str(Decimal)` or `<digits>e<exp>` form.
fn decimal_key(text: &str) -> Option<Box<str>> {
    let lower = text.to_ascii_lowercase();
    let (neg, body) = match lower.strip_prefix('-') {
        Some(rest) => (true, rest),
        None => (false, lower.trim_start_matches('+')),
    };
    let sign = if neg { "-" } else { "" };
    if body.contains("nan") {
        return None;
    }
    if body.starts_with("inf") {
        return Some(format!("{sign}inf").into());
    }
    let (mantissa, exp) = match body.split_once('e') {
        Some((m, e)) => (m, e.parse::<i64>().ok()?),
        None => (body, 0),
    };
    let (int, frac) = mantissa.split_once('.').unwrap_or((mantissa, ""));
    let digits = format!("{int}{frac}");
    let digits = digits.trim_start_matches('0');
    let trimmed = digits.trim_end_matches('0');
    if trimmed.is_empty() {
        return Some("0".into());
    }
    let dropped = i64::try_from(digits.len() - trimmed.len()).ok()?;
    let exp = exp + dropped - i64::try_from(frac.len()).ok()?;
    Some(format!("{sign}{trimmed}e{exp}").into())
}

/// The [`Decimal::key`] of `f`'s exact binary value, for `Decimal == float`.
pub(crate) fn float_decimal_key(f: f64) -> Option<Box<str>> {
    if !f.is_finite() {
        return decimal_key(&f.to_string());
    }
    let bits = f.to_bits();
    let sign = if bits >> 63 == 1 { "-" } else { "" };
    let biased = i64::try_from((bits >> 52) & 0x7ff).expect("11 bits fit i64");
    let fraction = bits & ((1 << 52) - 1);
    let (m, e) = if biased == 0 {
        (fraction, -1074)
    } else {
        (fraction | 1 << 52, biased - 1075)
    };
    let m = BigInt::from(m);
    let text = match u32::try_from(-e) {
        Ok(neg_e) => format!("{sign}{}e{e}", m * BigInt::from(5).pow(neg_e)),
        Err(_) => format!("{sign}{}", m << e),
    };
    decimal_key(&text)
}

/// `uuid.UUID(text).int`, or `None` where that raises.
pub(crate) fn parse_uuid(text: &str) -> Option<u128> {
    let hex = text.replace("urn:", "").replace("uuid:", "");
    let hex = hex.trim_matches(|c| c == '{' || c == '}').replace('-', "");
    (hex.len() == 32)
        .then(|| u128::from_str_radix(&hex, 16).ok())
        .flatten()
}

impl Leaf {
    /// The Python type `__name__`.
    #[must_use]
    pub fn type_name(&self) -> &'static str {
        match self {
            Leaf::Bytes(_) => "bytes",
            Leaf::Decimal(_) => "Decimal",
            Leaf::Uuid(_) => "UUID",
            Leaf::Complex(..) => "complex",
        }
    }

    fn rank(&self) -> u8 {
        match self {
            Leaf::Bytes(_) => 0,
            Leaf::Decimal(_) => 1,
            Leaf::Uuid(_) => 2,
            Leaf::Complex(..) => 3,
        }
    }

    /// A total order for canonical set order: by kind, then by value.
    pub(crate) fn total_cmp(&self, other: &Self) -> std::cmp::Ordering {
        let by_value = match (self, other) {
            (Leaf::Bytes(a), Leaf::Bytes(b)) => a.cmp(b),
            (Leaf::Decimal(a), Leaf::Decimal(b)) => a
                .approx
                .total_cmp(&b.approx)
                .then_with(|| a.text.cmp(&b.text)),
            (Leaf::Uuid(a), Leaf::Uuid(b)) => a.cmp(b),
            (Leaf::Complex(ar, ai), Leaf::Complex(br, bi)) => {
                ar.total_cmp(br).then_with(|| ai.total_cmp(bi))
            }
            _ => std::cmp::Ordering::Equal,
        };
        self.rank().cmp(&other.rank()).then(by_value)
    }
}

/// Python `==` within one kind; a `NaN` decimal equals nothing.
impl PartialEq for Leaf {
    #[allow(
        clippy::float_cmp,
        reason = "Python `complex ==` compares both parts exactly"
    )]
    fn eq(&self, other: &Self) -> bool {
        match (self, other) {
            (Leaf::Bytes(a), Leaf::Bytes(b)) => a == b,
            (Leaf::Decimal(a), Leaf::Decimal(b)) => a.key.is_some() && a.key == b.key,
            (Leaf::Uuid(a), Leaf::Uuid(b)) => a == b,
            (Leaf::Complex(ar, ai), Leaf::Complex(br, bi)) => ar == br && ai == bi,
            _ => false,
        }
    }
}

impl Decimal {
    /// Whether `as_tuple().exponent == 0`: the text is a plain integer.
    #[must_use]
    pub fn is_integral_text(&self) -> bool {
        let digits = self.text.trim_start_matches('-');
        !digits.is_empty() && digits.bytes().all(|b| b.is_ascii_digit())
    }
}

/// `str(uuid.UUID(int=value))`.
#[must_use]
pub fn uuid_string(value: u128) -> String {
    let hex = format!("{value:032x}");
    format!(
        "{}-{}-{}-{}-{}",
        &hex[..8],
        &hex[8..12],
        &hex[12..16],
        &hex[16..20],
        &hex[20..]
    )
}

/// Standard padded base64, as `DeepDiff` writes non-UTF-8 `bytes` to JSON.
fn base64(bytes: &[u8]) -> String {
    const ALPHABET: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(bytes.len().div_ceil(3) * 4);
    for chunk in bytes.chunks(3) {
        let n = chunk
            .iter()
            .enumerate()
            .fold(0u32, |n, (i, &b)| n | u32::from(b) << (16 - 8 * i));
        for i in 0..4 {
            out.push(if i <= chunk.len() {
                char::from(ALPHABET[(n >> (18 - 6 * i) & 63) as usize])
            } else {
                '='
            });
        }
    }
    out
}

impl Leaf {
    /// `DeepDiff.to_json()`'s form: `bytes` as UTF-8 text or base64, a
    /// `Decimal` as an int or float, a `UUID` as its `str()`. A `complex`,
    /// which `DeepDiff` refuses, becomes its `repr()`.
    #[must_use]
    pub fn to_serde_json(&self) -> serde_json::Value {
        use serde_json::Value as J;
        match self {
            Leaf::Bytes(b) => {
                J::String(std::str::from_utf8(b).map_or_else(|_| base64(b), str::to_owned))
            }
            Leaf::Decimal(d) => match d.text.parse::<i64>() {
                Ok(i) if d.is_integral_text() => J::from(i),
                _ => serde_json::Number::from_f64(d.approx).map_or(J::Null, J::Number),
            },
            Leaf::Uuid(u) => J::String(uuid_string(*u)),
            Leaf::Complex(re, im) => J::String(complex_repr(*re, *im)),
        }
    }
}

impl Decimal {
    /// The integer this decimal equals, or `None` for a fraction, a
    /// non-finite value, or a magnitude beyond `10**400`.
    pub(crate) fn integer(&self) -> Option<BigInt> {
        let key = self.key()?;
        if key == "0" {
            return Some(BigInt::from(0));
        }
        let (digits, exp) = key.split_once('e')?;
        let exp = exp.parse::<usize>().ok().filter(|e| *e <= 400)?;
        format!("{digits}{}", "0".repeat(exp)).parse().ok()
    }
}

#[cfg(test)]
#[path = "leaf_tests.rs"]
mod tests;
