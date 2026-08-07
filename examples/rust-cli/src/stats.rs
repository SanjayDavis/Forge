// Proof #4: Rust CLI — per-column statistics engine.
use std::fmt;

#[derive(Debug, Clone)]
pub struct ColumnStats {
    pub name: String,
    pub count: usize,   // non-empty cells
    pub numeric: usize, // cells that parsed as f64
    pub sum: Option<f64>,
    pub mean: Option<f64>,
    pub median: Option<f64>,
    pub min: Option<f64>,
    pub max: Option<f64>,
}

pub fn column_stats(rows: &[Vec<String>], col: usize, name: String) -> ColumnStats {
    let mut count = 0usize;
    let mut nums: Vec<f64> = Vec::new();
    for row in rows {
        if let Some(cell) = row.get(col) {
            let t = cell.trim();
            if !t.is_empty() {
                count += 1;
                if let Ok(v) = t.parse::<f64>() {
                    nums.push(v);
                }
            }
        }
    }
    if nums.is_empty() {
        return ColumnStats {
            name,
            count,
            numeric: 0,
            sum: None,
            mean: None,
            median: None,
            min: None,
            max: None,
        };
    }
    nums.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let numeric = nums.len();
    let sum: f64 = nums.iter().sum();
    let mean = sum / numeric as f64;
    let median = if numeric % 2 == 1 {
        nums[numeric / 2]
    } else {
        (nums[numeric / 2 - 1] + nums[numeric / 2]) / 2.0
    };
    let min = nums[0];
    let max = nums[numeric - 1];
    ColumnStats {
        name,
        count,
        numeric,
        sum: Some(sum),
        mean: Some(mean),
        median: Some(median),
        min: Some(min),
        max: Some(max),
    }
}

pub fn stats_all(rows: &[Vec<String>], header: &[String]) -> Vec<ColumnStats> {
    let cols = rows.iter().map(|r| r.len()).max().unwrap_or(0).max(header.len());
    (0..cols)
        .map(|c| {
            let name = header
                .get(c)
                .cloned()
                .unwrap_or_else(|| format!("col {}", c + 1));
            column_stats(rows, c, name)
        })
        .collect()
}

impl fmt::Display for ColumnStats {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let fmt_opt = |o: &Option<f64>| {
            o.map(|v| format!("{v}")).unwrap_or_else(|| "n/a".to_string())
        };
        write!(
            f,
            "{}: count={} sum={} mean={} median={} min={} max={}",
            self.name,
            self.count,
            fmt_opt(&self.sum),
            fmt_opt(&self.mean),
            fmt_opt(&self.median),
            fmt_opt(&self.min),
            fmt_opt(&self.max)
        )
    }
}

#[cfg(test)]
mod unit {
    use super::*;

    fn row(cells: &[&str]) -> Vec<String> {
        cells.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn known_column() {
        let rows = vec![row(&["1"]), row(&["2"]), row(&["3"]), row(&["4"])];
        let s = column_stats(&rows, 0, "x".into());
        assert_eq!(s.count, 4);
        assert_eq!(s.sum, Some(10.0));
        assert_eq!(s.mean, Some(2.5));
        assert_eq!(s.median, Some(2.5));
        assert_eq!(s.min, Some(1.0));
        assert_eq!(s.max, Some(4.0));
    }

    #[test]
    fn odd_median() {
        let rows = vec![row(&["1"]), row(&["2"]), row(&["3"])];
        assert_eq!(column_stats(&rows, 0, "x".into()).median, Some(2.0));
    }

    #[test]
    fn mixed_column() {
        let rows = vec![row(&["1"]), row(&["x"]), row(&["3"])];
        let s = column_stats(&rows, 0, "x".into());
        assert_eq!(s.count, 3);
        assert_eq!(s.numeric, 2);
        assert_eq!(s.mean, Some(2.0));
    }

    #[test]
    fn all_string_column() {
        let rows = vec![row(&["a"]), row(&["b"])];
        let s = column_stats(&rows, 0, "x".into());
        assert!(s.sum.is_none());
        assert!(s.mean.is_none());
    }

    #[test]
    fn empty_column() {
        let rows = vec![row(&[""]), row(&[""])];
        let s = column_stats(&rows, 0, "x".into());
        assert_eq!(s.count, 0);
        assert!(s.max.is_none());
    }

    #[test]
    fn negative_and_decimals() {
        let rows = vec![row(&["-3.5"]), row(&["2.5"]), row(&["1.5"])];
        let s = column_stats(&rows, 0, "x".into());
        assert_eq!(s.min, Some(-3.5));
        assert_eq!(s.max, Some(2.5));
        assert_eq!(s.sum, Some(0.5));
    }

    #[test]
    fn single_row() {
        let rows = vec![row(&["7"])];
        let s = column_stats(&rows, 0, "x".into());
        assert_eq!(s.median, Some(7.0));
        assert_eq!(s.min, Some(7.0));
    }
}