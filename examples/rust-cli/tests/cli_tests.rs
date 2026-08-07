// Proof #4: Rust CLI — CLI integration tests against the real binary.
// CARGO_BIN_EXE_rcli is provided by cargo for integration tests.
use std::process::Command;

fn rcli() -> Command {
    Command::new(env!("CARGO_BIN_EXE_rcli"))
}

#[test]
fn stats_on_numbers_fixture() {
    let out = rcli()
        .args(["stats", "fixtures/numbers.csv"])
        .output()
        .unwrap();
    assert!(out.status.success(), "stderr: {}", String::from_utf8_lossy(&out.stderr));
    let text = String::from_utf8_lossy(&out.stdout);
    assert!(text.contains("score: count=5"), "got: {text}");
    assert!(text.contains("mean=4.1"), "got: {text}");
}

#[test]
fn describe_on_mixed_fixture() {
    let out = rcli()
        .args(["describe", "fixtures/mixed.csv"])
        .output()
        .unwrap();
    assert!(out.status.success());
    let text = String::from_utf8_lossy(&out.stdout);
    assert!(text.contains("type=mixed"), "got: {text}");
}

#[test]
fn head_n_two_round_trips() {
    let out = rcli()
        .args(["head", "fixtures/quoted.csv", "-n", "2"])
        .output()
        .unwrap();
    assert!(out.status.success());
    let text = String::from_utf8_lossy(&out.stdout);
    assert!(text.contains("has, comma"), "got: {text}");
}

#[test]
fn missing_file_exits_1() {
    let out = rcli().args(["stats", "fixtures/nope.csv"]).output().unwrap();
    assert_eq!(out.status.code(), Some(1));
    let err = String::from_utf8_lossy(&out.stderr);
    assert!(err.starts_with("rcli:"), "got: {err}");
}

#[test]
fn unknown_subcommand_exits_2() {
    let out = rcli().args(["frobnicate", "x.csv"]).output().unwrap();
    assert_eq!(out.status.code(), Some(2));
    let err = String::from_utf8_lossy(&out.stderr);
    assert!(err.contains("unknown subcommand"), "got: {err}");
}

#[test]
fn help_exits_0() {
    let out = rcli().arg("--help").output().unwrap();
    assert!(out.status.success());
    assert!(String::from_utf8_lossy(&out.stdout).contains("USAGE"));
}