// Proof #4: Rust CLI — CSV parser integration tests (error positions).
use rcli::csv;
use rcli::error::RcliError;

#[test]
fn empty_input_is_empty_error() {
    match csv::parse("") {
        Err(RcliError::Empty) => {}
        other => panic!("expected Empty, got {other:?}"),
    }
}

#[test]
fn unclosed_quote_reports_position() {
    match csv::parse("a,b\n\"oops") {
        Err(RcliError::Parse { line, col, .. }) => {
            assert_eq!(line, 2, "unclosed quote is detected on line 2");
            assert_eq!(col, 6, "detected at end of input (col 6)");
        }
        other => panic!("expected Parse, got {other:?}"),
    }
}

#[test]
fn newline_inside_quotes_is_error() {
    assert!(matches!(
        csv::parse("a,\"x\ny\""),
        Err(RcliError::Parse { .. })
    ));
}

#[test]
fn trailing_newline_is_fine() {
    let rows = csv::parse("a,b\nc,d\n").unwrap();
    assert_eq!(rows.len(), 2);
}

#[test]
fn empty_fields_kept() {
    let rows = csv::parse("a,,c\n").unwrap();
    assert_eq!(rows[0].len(), 3);
    assert_eq!(rows[0][1], "");
}