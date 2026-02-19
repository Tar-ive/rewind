use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use rewind_finance::{amex_parser::parse_amex_csv, task_emitter::TaskEmitter};
use std::path::PathBuf;

mod setup;
mod state;

#[derive(Parser, Debug)]
#[command(name = "rewind", version, about = "Rewind Rust-native CLI")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// One-time interactive setup: capture goals and write ~/.rewind/*
    Setup,

    /// Generate a basic plan for today from goals + optional statement signals
    PlanDay {
        /// Optional AMEX CSV to include implicit finance signals
        #[arg(long)]
        csv: Option<PathBuf>,

        /// Limit number of tasks printed (default: 10)
        #[arg(long, default_value_t = 10)]
        limit: usize,
    },

    /// Finance-related commands
    Finance {
        #[command(subcommand)]
        command: FinanceCommand,
    },

    /// Run interactive auth flows via OpenClaw (TTY required)
    Auth {
        #[command(subcommand)]
        command: AuthCommand,
    },
}

#[derive(Subcommand, Debug)]
enum FinanceCommand {
    /// Parse an AMEX CSV and emit grouped tasks (deterministic)
    Sync {
        /// Path to AMEX CSV (defaults to ./amex.csv if present)
        #[arg(long)]
        csv: Option<PathBuf>,

        /// Account label (default: AMEX)
        #[arg(long, default_value = "AMEX")]
        account: String,
    },
}

#[derive(Subcommand, Debug)]
enum AuthCommand {
    /// Run `openclaw models auth setup-token --provider anthropic`
    ClaudeSetupToken,

    /// Run `openclaw models auth login --provider openai-codex`
    OpenaiOauth,
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Command::Setup => {
            setup::run_setup()?;
        }

        Command::PlanDay { csv, limit } => {
            plan_day(csv, limit)?;
        }

        Command::Finance { command } => match command {
            FinanceCommand::Sync { csv, account } => {
                let csv_path = csv.unwrap_or_else(default_amex_csv);
                if !csv_path.exists() {
                    bail!(
                        "CSV not found: {} (pass --csv <path>)",
                        csv_path.display()
                    );
                }

                let txns = parse_amex_csv(&csv_path)
                    .with_context(|| format!("parsing {}", csv_path.display()))?;

                let tasks = TaskEmitter::emit(&txns);
                let records = TaskEmitter::to_records(&txns, &account);

                println!("Parsed {} transactions from {}", txns.len(), csv_path.display());
                println!("Generated {} grouped tasks\n", tasks.len());

                for t in &tasks {
                    println!(
                        "[{:?}] urgency={:.2} | {} | count={} | total=${:.2}",
                        t.goal_tag,
                        t.urgency,
                        t.goal_name,
                        t.transaction_count,
                        t.total_amount.abs()
                    );
                }

                // Quick integration smoke check
                let expense_count = records.iter().filter(|r| r.is_expense()).count();
                println!("\nRecords: {} (expenses: {})", records.len(), expense_count);
            }
        },

        Command::Auth { command } => match command {
            AuthCommand::ClaudeSetupToken => {
                run_interactive(vec![
                    "openclaw",
                    "models",
                    "auth",
                    "setup-token",
                    "--provider",
                    "anthropic",
                ])?;
            }
            AuthCommand::OpenaiOauth => {
                run_interactive(vec![
                    "openclaw",
                    "models",
                    "auth",
                    "login",
                    "--provider",
                    "openai-codex",
                ])?;
            }
        },
    }

    Ok(())
}

fn default_amex_csv() -> PathBuf {
    // Prefer repo-root amex.csv when running from workspace
    PathBuf::from("amex.csv")
}

fn run_interactive(argv: Vec<&str>) -> Result<()> {
    let (bin, args) = argv.split_first().context("empty argv")?;

    let status = std::process::Command::new(bin)
        .args(args)
        .stdin(std::process::Stdio::inherit())
        .stdout(std::process::Stdio::inherit())
        .stderr(std::process::Stdio::inherit())
        .status()
        .with_context(|| format!("running {}", bin))?;

    if !status.success() {
        bail!("command failed with status: {}", status);
    }

    Ok(())
}

fn plan_day(csv: Option<PathBuf>, limit: usize) -> Result<()> {
    let goals_path = state::goals_path()?;
    if !goals_path.exists() {
        bail!(
            "No goals found at {}. Run: rewind setup",
            goals_path.display()
        );
    }

    let goals_md = state::read_goals_md(&goals_path)?;

    println!("# Plan for today\n");
    println!("Goals file: {}\n", goals_path.display());

    // Print goals (raw for now; later parse into structured goal objects)
    println!("## Goals (raw)\n");
    println!("{}\n", goals_md.trim());

    if let Some(csv_path) = csv.or_else(|| {
        let p = default_amex_csv();
        if p.exists() { Some(p) } else { None }
    }) {
        println!("## Implicit signals: finance (AMEX CSV)\n");
        let txns = parse_amex_csv(&csv_path)
            .with_context(|| format!("parsing {}", csv_path.display()))?;
        let tasks = TaskEmitter::emit(&txns);

        println!("Parsed {} transactions from {}", txns.len(), csv_path.display());
        println!("Top {} tasks:\n", limit);

        for t in tasks.iter().take(limit) {
            println!(
                "- [{:?}] urgency={:.2} | {} | count={} | total=${:.2}",
                t.goal_tag,
                t.urgency,
                t.goal_name,
                t.transaction_count,
                t.total_amount.abs()
            );
        }

        println!("\nNext: use intent classification to map these tasks to your explicit goals (LLM optional).\n");
    } else {
        println!("## Implicit signals\n\n(no statement provided; pass --csv <file>)\n");
    }

    println!("## Next actions\n");
    println!("- If you haven’t: `rewind auth claude-setup-token` (optional)");
    println!("- Import a statement: `rewind finance sync --csv <amex.csv>`");
    println!("- Re-run planning: `rewind plan-day --csv <amex.csv>`");

    Ok(())
}
