use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use rewind_finance::{amex_parser::parse_amex_csv, task_emitter::TaskEmitter};
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(name = "rewind", version, about = "Rewind Rust-native CLI")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
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
    let (bin, args) = argv
        .split_first()
        .context("empty argv")?;

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
