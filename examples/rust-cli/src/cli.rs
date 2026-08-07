// Proof #4: Rust CLI — hand-rolled argument parsing.
use std::path::PathBuf;

use crate::error::RcliError;

#[derive(Debug, PartialEq)]
pub enum Command {
    Stats(PathBuf),
    Describe(PathBuf),
    Head { path: PathBuf, n: usize },
}

pub fn parse_args(args: &[String]) -> Result<Command, RcliError> {
    if args.is_empty() {
        return Err(RcliError::Usage("missing subcommand".into()));
    }
    match args[0].as_str() {
        "stats" => {
            if args.len() < 2 {
                return Err(RcliError::Usage("stats requires a file path".into()));
            }
            Ok(Command::Stats(PathBuf::from(&args[1])))
        }
        "describe" => {
            if args.len() < 2 {
                return Err(RcliError::Usage("describe requires a file path".into()));
            }
            Ok(Command::Describe(PathBuf::from(&args[1])))
        }
        "head" => {
            if args.len() < 2 {
                return Err(RcliError::Usage("head requires a file path".into()));
            }
            let mut n = 10usize;
            let mut i = 2;
            while i < args.len() {
                match args[i].as_str() {
                    "-n" => {
                        if i + 1 >= args.len() {
                            return Err(RcliError::Usage("-n requires a value".into()));
                        }
                        match args[i + 1].parse::<usize>() {
                            Ok(v) => n = v,
                            Err(_) => {
                                return Err(RcliError::Usage(format!(
                                    "invalid -n value '{}'",
                                    args[i + 1]
                                )))
                            }
                        }
                        i += 2;
                    }
                    other => {
                        return Err(RcliError::Usage(format!("unknown option '{other}'")))
                    }
                }
            }
            Ok(Command::Head {
                path: PathBuf::from(&args[1]),
                n,
            })
        }
        other => Err(RcliError::Usage(format!("unknown subcommand '{other}'"))),
    }
}

#[cfg(test)]
mod unit {
    use super::*;

    fn s(v: &[&str]) -> Vec<String> {
        v.iter().map(|x| x.to_string()).collect()
    }

    #[test]
    fn stats_path() {
        assert_eq!(
            parse_args(&s(&["stats", "f.csv"])).unwrap(),
            Command::Stats(PathBuf::from("f.csv"))
        );
    }

    #[test]
    fn head_with_n() {
        assert_eq!(
            parse_args(&s(&["head", "f.csv", "-n", "2"])).unwrap(),
            Command::Head {
                path: PathBuf::from("f.csv"),
                n: 2
            }
        );
    }

    #[test]
    fn unknown_subcommand() {
        let e = parse_args(&s(&["frobnicate", "x"])).unwrap_err();
        assert!(e.to_string().contains("unknown subcommand"));
    }

    #[test]
    fn missing_path() {
        assert!(parse_args(&s(&["stats"])).is_err());
    }
}