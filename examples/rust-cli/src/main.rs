// Proof #4: Rust CLI — entry point: arg parsing, dispatch, exit codes.
// Exit codes: 0 success, 1 data/io error, 2 usage error.
use std::env;
use std::fs;
use std::process::ExitCode;

use rcli::cli::{self, Command};
use rcli::csv;
use rcli::error::RcliError;
use rcli::{describe, head, stats};

const USAGE: &str = "rcli — CSV statistics CLI (Proof #4)

USAGE:
    rcli stats <file>
    rcli describe <file>
    rcli head <file> [-n N]

SUBCOMMANDS:
    stats     per-column count/sum/mean/median/min/max
    describe  column types and row counts
    head      print the first N rows (default 10)

OPTIONS:
    -n N      number of rows for head
    --help    show this help
";

fn run() -> Result<String, RcliError> {
    let args: Vec<String> = env::args().skip(1).collect();
    match cli::parse_args(&args)? {
        Command::Stats(path) => {
            let text = fs::read_to_string(&path)?;
            let rows = csv::parse(&text)?;
            let header = rows.first().cloned().unwrap_or_default();
            let data = &rows[1..];
            let all = stats::stats_all(data, &header);
            Ok(all
                .iter()
                .map(|c| c.to_string())
                .collect::<Vec<_>>()
                .join("\n"))
        }
        Command::Describe(path) => {
            let text = fs::read_to_string(&path)?;
            let rows = csv::parse(&text)?;
            let header = rows.first().cloned().unwrap_or_default();
            let data = &rows[1..];
            Ok(describe::describe(data, &header))
        }
        Command::Head { path, n } => {
            let text = fs::read_to_string(&path)?;
            let rows = csv::parse(&text)?;
            let header = rows.first().cloned().unwrap_or_default();
            let data = &rows[1..];
            Ok(head::head(data, &header, n))
        }
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.iter().any(|a| a == "--help" || a == "help") {
        print!("{USAGE}");
        return ExitCode::SUCCESS;
    }
    match run() {
        Ok(out) => {
            println!("{out}");
            ExitCode::SUCCESS
        }
        Err(RcliError::Usage(m)) => {
            eprintln!("rcli: {m}");
            eprintln!("try: rcli --help");
            ExitCode::from(2)
        }
        Err(e) => {
            eprintln!("rcli: {e}");
            ExitCode::from(1)
        }
    }
}
