use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use rewind_finance::{amex_parser::parse_amex_csv, task_emitter::TaskEmitter};
use std::path::PathBuf;

mod auth;
mod calendar;
mod onboard;
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

    /// Create time-blocked calendar events from the current plan/schedule
    Calendar {
        #[command(subcommand)]
        command: CalendarCommand,
    },

    /// Finance-related commands
    Finance {
        #[command(subcommand)]
        command: FinanceCommand,
    },

    /// Onboarding helper: outputs ONLY JSON with next question or proceed=true
    Onboard {
        #[command(subcommand)]
        command: OnboardCommand,
    },

    /// Auth (optional)
    Auth {
        #[command(subcommand)]
        command: AuthCommand,
    },
}

#[derive(Subcommand, Debug)]
enum CalendarCommand {
    /// Export time-blocked schedule as ICS (prints to stdout)
    ExportIcs {
        /// AMEX CSV to derive finance tasks (optional)
        #[arg(long)]
        csv: Option<PathBuf>,

        /// Number of finance tasks to schedule
        #[arg(long, default_value_t = 10)]
        limit: usize,

        /// Energy level (1-5)
        #[arg(long, default_value_t = 5)]
        energy: i32,

        /// Event title prefix
        #[arg(long, default_value = "Rewind: STS: ")]
        prefix: String,
    },

    /// Push calendar events to Google Calendar using gcalcli import
    PushGcalcli {
        /// AMEX CSV to derive finance tasks (optional)
        #[arg(long)]
        csv: Option<PathBuf>,

        /// Number of finance tasks to schedule
        #[arg(long, default_value_t = 10)]
        limit: usize,

        /// Energy level (1-5)
        #[arg(long, default_value_t = 5)]
        energy: i32,

        /// Target calendar name (optional)
        #[arg(long)]
        calendar: Option<String>,

        /// Event title prefix
        #[arg(long, default_value = "Rewind: STS: ")]
        prefix: String,
    },
}

#[derive(Subcommand, Debug)]
enum OnboardCommand {
    /// Output ONLY JSON: proceed_to_planning + assistant_message
    Decide {
        /// Optional statement path (if you already have one)
        #[arg(long)]
        statement: Option<PathBuf>,
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
    /// Run Claude Code's OAuth flow (requires `claude` CLI installed)
    ClaudeSetupToken,

    /// Paste and store an Anthropic API token into ~/.rewind/auth.json
    PasteAnthropicToken,

    /// Paste and store an OpenAI API key into ~/.rewind/auth.json
    PasteOpenaiApiKey,
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

        Command::Calendar { command } => match command {
            CalendarCommand::ExportIcs { csv, limit, energy, prefix } => {
                let ics = calendar_build_ics(csv, limit, energy, &prefix)?;
                print!("{}", ics);
            }
            CalendarCommand::PushGcalcli { csv, limit, energy, calendar: cal, prefix } => {
                let ics = calendar_build_ics(csv, limit, energy, &prefix)?;
                calendar::push_ics_via_gcalcli(&ics, cal.as_deref())?;
            }
        },

        Command::Onboard { command } => match command {
            OnboardCommand::Decide { statement } => {
                let profile = state::read_profile().ok();
                let tz = profile.as_ref().map(|p| p.timezone.clone());

                let goals_path = state::goals_path().ok();
                let has_goals = goals_path.as_ref().is_some_and(|p| p.exists());

                let has_statement = statement.as_ref().is_some_and(|p| p.exists());

                let decision = onboard::decide_next_question(&onboard::OnboardState {
                    timezone: tz,
                    has_goals,
                    has_statement,
                });

                // Strict: output only JSON
                println!("{}", serde_json::to_string(&decision)?);
            }
        },

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
                auth::claude_setup_token()?;
            }
            AuthCommand::PasteAnthropicToken => {
                auth::anthropic_paste_token()?;
            }
            AuthCommand::PasteOpenaiApiKey => {
                auth::openai_paste_api_key()?;
            }
        },
    }

    Ok(())
}

fn default_amex_csv() -> PathBuf {
    // Prefer repo-root amex.csv when running from workspace
    PathBuf::from("amex.csv")
}

fn calendar_build_ics(csv: Option<PathBuf>, limit: usize, energy: i32, prefix: &str) -> Result<String> {
    let profile = state::read_profile()?;
    let tz: chrono_tz::Tz = profile
        .timezone
        .parse()
        .map_err(|_| anyhow::anyhow!("invalid timezone in profile.json: {}", profile.timezone))?;

    // Use finance tasks from AMEX as our initial task source.
    // Later we will merge: deadlines + goal-derived tasks + finance + other signals.
    let csv_path = csv.unwrap_or_else(default_amex_csv);
    if !csv_path.exists() {
        bail!("CSV not found: {} (pass --csv <path>)", csv_path.display());
    }

    let txns = parse_amex_csv(&csv_path)
        .with_context(|| format!("parsing {}", csv_path.display()))?;
    let finance_tasks = TaskEmitter::emit(&txns);

    // Convert into core Tasks, enqueue into STS, then order.
    let now = chrono::Utc::now();
    let mut sts = rewind_core::ShortTermScheduler::new();

    for (i, ft) in finance_tasks.iter().take(limit).enumerate() {
        // Same heuristic as our regression tests.
        let mut minutes = 15 + (ft.transaction_count as i32 / 10) * 5;
        if ft.total_amount.abs() > 1000.0 {
            minutes += 15;
        }
        minutes = minutes.clamp(10, 90);

        let (energy_cost, cognitive_load) = match ft.category {
            rewind_core::Category::CreditCard | rewind_core::Category::Tuition => (4, 4),
            rewind_core::Category::Savings => (3, 3),
            _ => (2, 2),
        };

        let urgency = (ft.urgency * 10.0).round() as i32;

        let mut title = ft.goal_name.clone();
        if !ft.sample_descriptions.is_empty() {
            title.push_str(" | ");
            title.push_str(&ft.sample_descriptions.join(" ; "));
        }

        let mut t = rewind_core::Task::new(format!("cal-{:04}", i), title)
            .with_duration(minutes)
            .with_energy(energy_cost)
            .with_cognitive(cognitive_load)
            .with_deadline_urgency(urgency);

        // If finance task horizon is short, give it a 24h soft deadline for visualization
        if ft.goal_tag == rewind_core::GoalTag::Short {
            t.deadline = Some(now + chrono::Duration::hours(24));
        }

        sts.enqueue(t, now);
    }

    let ordered = calendar::order_tasks_via_sts(sts, energy);
    let events = calendar::tasks_to_timeblocks(&ordered, tz, now, prefix);
    Ok(calendar::events_to_ics(&events))
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

    let profile = state::read_profile()?;

    // Temporal context (OpenClaw-style: always anchor to 'now' + timezone)
    let tz: chrono_tz::Tz = profile
        .timezone
        .parse()
        .map_err(|_| anyhow::anyhow!("invalid timezone in profile.json: {}", profile.timezone))?;
    let now_utc = chrono::Utc::now();
    let now_local = now_utc.with_timezone(&tz);

    println!("# Plan for today\n");
    println!("Now: {} ({})", now_local.format("%Y-%m-%d %H:%M"), profile.timezone);
    println!("Now (UTC): {}\n", now_utc.to_rfc3339());
    println!("Goals file: {}\n", goals_path.display());

    // Parse goals into structured objects (deterministic)
    let goals = rewind_core::parse_goals_md(&goals_md);
    println!("## Goals\n");
    for g in &goals {
        println!("- [{:?}] {}", g.horizon, g.text);
    }
    println!();

    if let Some(csv_path) = csv.or_else(|| {
        let p = default_amex_csv();
        if p.exists() { Some(p) } else { None }
    }) {
        println!("## Implicit signals: finance (AMEX CSV)\n");
        let txns = parse_amex_csv(&csv_path)
            .with_context(|| format!("parsing {}", csv_path.display()))?;
        let tasks = TaskEmitter::emit(&txns);

        // Statement temporal range
        let min_date = txns.iter().map(|t| t.date).min().unwrap();
        let max_date = txns.iter().map(|t| t.date).max().unwrap();

        println!("Parsed {} transactions from {}", txns.len(), csv_path.display());
        println!("Statement range: {} → {}\n", min_date, max_date);
        println!("Top {} tasks:\n", limit);

        for t in tasks.iter().take(limit) {
            let mut title = t.goal_name.clone();
            if !t.sample_descriptions.is_empty() {
                title.push_str(" | ");
                title.push_str(&t.sample_descriptions.join(" ; "));
            }

            let task_like = rewind_core::TaskLike {
                title,
                horizon_hint: Some(match t.goal_tag {
                    rewind_core::GoalTag::Long => rewind_core::Horizon::Long,
                    rewind_core::GoalTag::Medium => rewind_core::Horizon::Medium,
                    rewind_core::GoalTag::Short => rewind_core::Horizon::Short,
                }),
            };
            let route = rewind_core::route_task(&task_like, &goals);

            let routed = match route.goal_index {
                Some(i) => format!("→ [{:?}] {} ({:?}, {})", goals[i].horizon, goals[i].text, route.confidence, route.reason),
                None => format!("→ (unrouted) ({:?}, {})", route.confidence, route.reason),
            };

            println!(
                "- [{:?}] urgency={:.2} | {} | count={} | total=${:.2} {}",
                t.goal_tag,
                t.urgency,
                t.goal_name,
                t.transaction_count,
                t.total_amount.abs(),
                routed
            );
        }

        println!("\nNext: run intent classification only for low-confidence/unrouted tasks (LLM optional).\n");
    } else {
        println!("## Implicit signals\n\n(no statement provided; pass --csv <file>)\n");
    }

    println!("## Next actions\n");
    println!("- If you haven't: rewind auth claude-setup-token (optional)");
    println!("- Import a statement: rewind finance sync --csv <amex.csv>");
    println!("- Re-run planning: rewind plan-day --csv <amex.csv>");

    Ok(())
}
