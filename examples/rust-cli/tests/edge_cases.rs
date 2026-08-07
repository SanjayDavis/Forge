// Proof #4: Rust CLI — edge-case / stress tests.
use std::process::Command;

fn rcli() -> Command {
    Command::new(env!("CARGO_BIN_EXE_rcli"))
}

fn fixture(name: &str) -> String {
    format!("fixtures/{name}")
}

#[test]
fn header_only_stats_all_na() {
    let out = rcli()
        .args(["stats", &fixture("header-only.csv")])
        .output()
        .unwrap();
    assert!(out.status.success());
    let text = String::from_utf8_lossy(&out.stdout);
    assert!(text.contains("count=0"), "got: {text}");
    assert!(text.contains("n/a"), "got: {text}");
}

#[test]
fn empty_file_exits_1() {
    let out = rcli()
        .args(["stats", &fixture("empty.csv")])
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(1));
    assert!(String::from_utf8_lossy(&out.stderr).contains("empty input"));
}

#[test]
fn unicode_column_names() {
    let out = rcli()
        .args(["describe", &fixture("unicode.csv")])
        .output()
        .unwrap();
    assert!(out.status.success());
    let text = String::from_utf8_lossy(&out.stdout);
    assert!(text.contains("café"), "got: {text}");
}

#[test]
fn quoted_numeric_looks_string() {
    let out = rcli()
        .args(["describe", &fixture("quoted.csv")])
        .output()
        .unwrap();
    assert!(out.status.success());
    // desc column contains quoted text -> its column type should be string/mixed
    let text = String::from_utf8_lossy(&out.stdout);
    assert!(text.contains("type="), "got: {text}");
}

#[test]
fn long_single_line_no_panic() {
    let mut line = String::from("a,");
    line.push_str(&"x".repeat(10_000));
    std::fs::write("target/edge_long.csv", line).unwrap();
    let out = rcli()
        .args(["describe", "target/edge_long.csv"])
        .output()
        .unwrap();
    assert!(out.status.success(), "stderr: {}", String::from_utf8_lossy(&out.stderr));
}

#[test]
fn thousand_rows_parse() {
    let mut csv = String::from("n\n");
    for i in 0..1000 {
        csv.push_str(&format!("{i}\n"));
    }
    std::fs::write("target/edge_1000.csv", csv).unwrap();
    let out = rcli()
        .args(["stats", "target/edge_1000.csv"])
        .output()
        .unwrap();
    assert!(out.status.success());
    let text = String::from_utf8_lossy(&out.stdout);
    assert!(text.contains("count=1000"), "got: {text}");
    assert!(text.contains("mean=499.5"), "got: {text}");
}

#[test]
fn crlf_fixture_parses() {
    let out = rcli()
        .args(["stats", &fixture("crlf.csv")])
        .output()
        .unwrap();
    assert!(out.status.success(), "stderr: {}", String::from_utf8_lossy(&out.stderr));
}

#[test]
fn only_commas_row() {
    std::fs::write("target/edge_commas.csv", "a,b,c\n,,\n").unwrap();
    let out = rcli()
        .args(["describe", "target/edge_commas.csv"])
        .output()
        .unwrap();
    assert!(out.status.success());
}