// Proof #4: Rust CLI — describe subcommand: per-column type inference.
pub fn describe(rows: &[Vec<String>], header: &[String]) -> String {
    let cols = rows
        .iter()
        .map(|r| r.len())
        .max()
        .unwrap_or(0)
        .max(header.len());
    let mut out = String::new();
    for c in 0..cols {
        let name = header
            .get(c)
            .cloned()
            .unwrap_or_else(|| format!("col {}", c + 1));
        let mut non_empty = 0usize;
        let mut numeric = 0usize;
        let mut stringy = 0usize;
        for row in rows {
            if let Some(cell) = row.get(c) {
                let t = cell.trim();
                if !t.is_empty() {
                    non_empty += 1;
                    if t.parse::<f64>().is_ok() {
                        numeric += 1;
                    } else {
                        stringy += 1;
                    }
                }
            }
        }
        let kind = if non_empty == 0 {
            "empty"
        } else if stringy == 0 {
            "numeric"
        } else if numeric == 0 {
            "string"
        } else {
            "mixed"
        };
        out.push_str(&format!(
            "{name}: rows={} non_empty={} type={kind}\n",
            rows.len(),
            non_empty
        ));
    }
    out.push_str(&format!("file: {} data rows, {cols} columns", rows.len()));
    out
}

#[cfg(test)]
mod unit {
    use super::*;

    fn v(cells: &[&str]) -> Vec<String> {
        cells.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn numeric_column() {
        let out = describe(&[v(&["1"]), v(&["2"])], &v(&["x"]));
        assert!(out.contains("type=numeric"));
    }

    #[test]
    fn mixed_column() {
        let out = describe(&[v(&["1"]), v(&["a"])], &v(&["x"]));
        assert!(out.contains("type=mixed"));
    }

    #[test]
    fn empty_data_rows() {
        let out = describe(&[], &v(&["x", "y"]));
        assert!(out.contains("0 data rows"));
        assert!(out.contains("type=empty"));
    }

    #[test]
    fn summary_line() {
        let out = describe(&[v(&["1", "2"])], &v(&["a", "b"]));
        assert!(out.ends_with("file: 1 data rows, 2 columns"));
    }
}