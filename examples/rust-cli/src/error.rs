// Proof #4: Rust CLI — error types.
use std::fmt;
use std::io;

#[derive(Debug)]
pub enum RcliError {
    Io(io::Error),
    Parse { line: usize, col: usize, msg: String },
    Empty,
    Usage(String),
}

impl fmt::Display for RcliError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            RcliError::Io(e) => write!(f, "{e}"),
            RcliError::Parse { line, col, msg } => {
                write!(f, "line {line}, column {col}: {msg}")
            }
            RcliError::Empty => write!(f, "empty input"),
            RcliError::Usage(m) => write!(f, "{m}"),
        }
    }
}

impl std::error::Error for RcliError {}

impl From<io::Error> for RcliError {
    fn from(e: io::Error) -> Self {
        RcliError::Io(e)
    }
}