use super::*;

#[test]
fn decimal_key_folds_python_equal_text() {
    let key = |t: &str| Decimal::new(t).key().map(str::to_owned);
    assert_eq!(key("1.10"), key("1.1"));
    assert_eq!(key("100"), key("1E+2"));
    assert_eq!(key("-0"), key("0.000"));
    assert_ne!(key("1.1"), key("-1.1"));
    assert_eq!(key("NaN"), None);
    assert_eq!(key("-Infinity").as_deref(), Some("-inf"));
}

#[test]
fn float_key_is_the_exact_binary_value() {
    assert_eq!(
        float_decimal_key(0.5).as_deref(),
        Decimal::new("0.50").key()
    );
    assert_ne!(float_decimal_key(0.1).as_deref(), Decimal::new("0.1").key());
    assert_eq!(float_decimal_key(8.0).as_deref(), Decimal::new("8").key());
}

#[test]
fn parse_uuid_accepts_what_uuid_accepts() {
    let hex = "12345678-1234-5678-1234-567812345678";
    let int = 0x1234_5678_1234_5678_1234_5678_1234_5678;
    assert_eq!(parse_uuid(hex), Some(int));
    assert_eq!(parse_uuid(&format!("{{{hex}}}")), Some(int));
    assert_eq!(parse_uuid(&format!("urn:uuid:{hex}")), Some(int));
    assert_eq!(parse_uuid("zz"), None);
    assert_eq!(uuid_string(int), hex);
}
