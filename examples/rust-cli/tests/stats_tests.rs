// Proof #4: Rust CLI — stats engine integration tests.
use rcli::stats::{column_stats, stats_all};

fn v(cells: &[&str]) -> Vec<String> {
    cells.iter().map(|s| s.to_string()).collect()
}

#[test]
fn even_median() {
    let rows = vec![v(&["1"]), v(&["2"]), v(&["3"]), v(&["4"])];
    assert_eq!(column_stats(&rows, 0, "x".into()).median, Some(2.5));
}

#[test]
fn odd_median_is_middle() {
    let rows = vec![v(&["1"]), v(&["2"]), v(&["3"])];
    assert_eq!(column_stats(&rows, 0, "x".into()).median, Some(2.0));
}

#[test]
fn stats_all_uses_header() {
    let rows = vec![v(&["1", "a"])];
    let header = v(&["num", "txt"]);
    let all = stats_all(&rows, &header);
    assert_eq!(all.len(), 2);
    assert_eq!(all[0].name, "num");
    assert_eq!(all[1].name, "txt");
}

#[test]
fn stats_all_fallback_names() {
    let rows = vec![v(&["1"])];
    let all = stats_all(&rows, &[]);
    assert_eq!(all[0].name, "col 1");
}

#[test]
fn header_longer_than_data() {
    let rows: Vec<Vec<String>> = vec![];
    let all = stats_all(&rows, &v(&["a", "b", "c"]));
    assert_eq!(all.len(), 3);
    for s in &all {
        assert_eq!(s.count, 0);
        assert!(s.max.is_none());
    }
}