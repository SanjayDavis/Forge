// Proof #4: Rust CLI — head subcommand: header + first N rows, re-quoted.
pub fn head(rows: &[Vec<String>], header: &[String], n: usize) -> String {
    let mut out = String::new();
    if !header.is_empty() {
        out.push_str(&render_row(header));
        out.push('\n');
    }
    for row in rows.iter().take(n) {
        out.push_str(&render_row(row));
        out.push('\n');
    }
    out
}

fn render_row(row: &[String]) -> String {
    let cells: Vec<String> = row
        .iter()
        .map(|c| {
            if c.contains(',') || c.contains('"') || c.contains('\n') {
                format!("\"{}\"", c.replace('"', "\"\""))
            } else {
                c.clone()
            }
        })
        .collect();
    cells.join(",")
}

#[cfg(test)]
mod unit {
    use super::*;

    fn v(cells: &[&str]) -> Vec<String> {
        cells.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn head_two() {
        let rows = vec![v(&["1", "a"]), v(&["2", "b"]), v(&["3", "c"])];
        let out = head(&rows, &v(&["n", "s"]), 2);
        assert_eq!(out, "n,s\n1,a\n2,b\n");
    }

    #[test]
    fn zero_is_header_only() {
        let rows = vec![v(&["1", "a"])];
        assert_eq!(head(&rows, &v(&["n", "s"]), 0), "n,s\n");
    }

    #[test]
    fn large_n_returns_all() {
        let rows = vec![v(&["1", "a"])];
        assert_eq!(head(&rows, &v(&["n", "s"]), 100), "n,s\n1,a\n");
    }

    #[test]
    fn requoting_round_trips() {
        let rows = vec![v(&["1", "has, comma"]), v(&["2", "say \"hi\""])];
        let out = head(&rows, &v(&["n", "s"]), 2);
        assert_eq!(out, "n,s\n1,\"has, comma\"\n2,\"say \"\"hi\"\"\"\n");
    }
}