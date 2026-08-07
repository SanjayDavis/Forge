// Proof #4: Rust CLI — hand-rolled CSV parser with positioned errors.
// Supports: comma-separated fields, double-quoted fields (commas allowed),
// doubled-quote escaping inside quotes, CRLF/LF terminators, blank-line
// skipping. Newlines inside quoted fields are an error (positions tracked).
use crate::error::RcliError;

pub fn parse(input: &str) -> Result<Vec<Vec<String>>, RcliError> {
    let mut rows: Vec<Vec<String>> = Vec::new();
    let mut row: Vec<String> = Vec::new();
    let mut field = String::new();
    let mut line = 1usize;
    let mut col = 1usize;
    let mut in_quotes = false;
    let mut row_started = false;
    let mut chars = input.chars().peekable();

    if input.is_empty() {
        return Err(RcliError::Empty);
    }

    while let Some(c) = chars.next() {
        if in_quotes {
            match c {
                '"' => {
                    if chars.peek() == Some(&'"') {
                        // doubled quote inside a quoted field -> literal quote
                        field.push('"');
                        chars.next();
                        col += 2;
                    } else {
                        in_quotes = false;
                        col += 1;
                    }
                }
                '\n' => {
                    return Err(RcliError::Parse {
                        line,
                        col,
                        msg: "newline inside quoted field".into(),
                    })
                }
                _ => {
                    field.push(c);
                    col += 1;
                }
            }
            continue;
        }
        match c {
            '"' => {
                in_quotes = true;
                row_started = true;
                col += 1;
            }
            ',' => {
                row.push(std::mem::take(&mut field));
                row_started = true;
                col += 1;
            }
            '\n' | '\r' => {
                // A row ends at newline. Only emit it if the line actually
                // started (any field content or a field was begun); a truly
                // blank line must not leave a phantom empty row behind.
                if row_started || !field.is_empty() {
                    row.push(std::mem::take(&mut field));
                    rows.push(std::mem::take(&mut row));
                } else {
                    field.clear();
                    row.clear();
                }
                row_started = false;
                line += 1;
                col = 1;
            }
            _ => {
                field.push(c);
                row_started = true;
                col += 1;
            }
        }
    }

    if in_quotes {
        return Err(RcliError::Parse { line, col, msg: "unclosed quoted field".into() });
    }
    // flush trailing field/row
    if !field.is_empty() || row_started {
        row.push(std::mem::take(&mut field));
        rows.push(row);
    }

    Ok(rows)
}

#[cfg(test)]
mod unit {
    use super::*;

    fn v(cells: &[&str]) -> Vec<String> {
        cells.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn basic_rows() {
        assert_eq!(
            parse("a,b\nc,d").unwrap(),
            vec![v(&["a", "b"]), v(&["c", "d"])]
        );
    }

    #[test]
    fn quoted_comma_stays_one_field() {
        assert_eq!(
            parse("x,\"has, comma\"\n").unwrap(),
            vec![v(&["x", "has, comma"])]
        );
    }

    #[test]
    fn escaped_quotes() {
        assert_eq!(parse("\"say \"\"hi\"\"\"\n").unwrap(), vec![v(&["say \"hi\""])]);
    }

    #[test]
    fn crlf_parses_like_lf() {
        assert_eq!(
            parse("a,b\r\nc,d\r\n").unwrap(),
            parse("a,b\nc,d\n").unwrap()
        );
    }

    #[test]
    fn blank_lines_skipped() {
        assert_eq!(parse("a\n\nb").unwrap(), vec![v(&["a"]), v(&["b"])]);
    }
}