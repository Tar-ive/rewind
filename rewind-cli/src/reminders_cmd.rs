use anyhow::{Context, Result};
use chrono::{Duration, Utc};
use std::collections::HashSet;
use clap::Subcommand;
use rewind_core::{
    Horizon, Priority, ReminderIntent, ReminderPolicy, ReminderSource, Task, parse_goals_md,
    project_task_reminders,
};
use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::{BufRead, BufReader, Write};

use crate::config::load_config;
use crate::state::{ensure_rewind_home, goals_path};

#[derive(Subcommand, Debug)]
pub enum RemindersCommand {
    /// Build reminder intents from goals and append to local queue
    Plan {
        /// Delivery target (phone/email). If omitted, uses config.reminders.default_recipient
        #[arg(long)]
        to: Option<String>,

        /// Channel label (default: from config, fallback imessage)
        #[arg(long)]
        channel: Option<String>,

        /// Max reminders to generate
        #[arg(long, default_value_t = 10)]
        limit: usize,

        /// Force reminders to be due now (for testing)
        #[arg(long, default_value_t = false)]
        due_now: bool,
    },

    /// List queued reminder intents
    List {
        #[arg(long, default_value_t = 20)]
        limit: usize,
    },

    /// Send a single iMessage reminder immediately (macOS only)
    SendImessage {
        #[arg(long)]
        to: String,

        #[arg(long)]
        text: String,
    },

    /// Dispatch due reminder intents from queue
    Dispatch {
        /// Dry-run only; do not actually send
        #[arg(long, default_value_t = false)]
        dry_run: bool,

        /// Max sends in one run (default from config.reminders.max_dispatch_per_run)
        #[arg(long)]
        limit: Option<usize>,

        /// Include reminders due within the next N minutes
        #[arg(long)]
        include_future_minutes: Option<i64>,
    },

    /// Queue status summary (due/future/sent)
    Status,

    /// Show reminder-related config and what to set
    ConfigCheck,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct QueuedIntent {
    recipient: String,
    channel: String,
    intent: ReminderIntent,
}

pub fn run(cmd: RemindersCommand) -> Result<()> {
    match cmd {
        RemindersCommand::Plan {
            to,
            channel,
            limit,
            due_now,
        } => plan(to, channel, limit, due_now),
        RemindersCommand::List { limit } => list(limit),
        RemindersCommand::SendImessage { to, text } => send_imessage(&to, &text),
        RemindersCommand::Dispatch {
            dry_run,
            limit,
            include_future_minutes,
        } => dispatch(dry_run, limit, include_future_minutes),
        RemindersCommand::Status => status(),
        RemindersCommand::ConfigCheck => config_check(),
    }
}

fn queue_path() -> Result<std::path::PathBuf> {
    Ok(ensure_rewind_home()?.join("reminders").join("intents.jsonl"))
}

fn sent_keys_path() -> Result<std::path::PathBuf> {
    Ok(ensure_rewind_home()?.join("reminders").join("sent_keys.txt"))
}

fn plan(to: Option<String>, channel: Option<String>, limit: usize, due_now: bool) -> Result<()> {
    let gp = goals_path()?;
    let md = fs::read_to_string(&gp).with_context(|| format!("read {}", gp.display()))?;
    let goals = parse_goals_md(&md);

    if goals.is_empty() {
        anyhow::bail!("no goals found in {}", gp.display());
    }

    let cfg = load_config()?;
    let resolved_to = to
        .or(cfg.reminders.default_recipient.clone())
        .ok_or_else(|| anyhow::anyhow!("No recipient set. Pass --to or set config.toml [reminders].default_recipient"))?;
    let resolved_channel = channel.unwrap_or(cfg.reminders.default_channel.clone());

    let now = Utc::now();
    let policy = ReminderPolicy::default();

    let mut emitted: Vec<QueuedIntent> = Vec::new();

    for (i, g) in goals.iter().enumerate() {
        let mut t = Task::new(format!("goal-{:04}", i), g.text.clone());
        match g.horizon {
            Horizon::Short => {
                t.priority = Priority::P1Important;
                t.deadline = Some(now + Duration::hours(12));
                t.deadline_urgency = 8;
            }
            Horizon::Medium => {
                t.priority = Priority::P2Normal;
                t.deadline = Some(now + Duration::days(3));
                t.deadline_urgency = 5;
            }
            Horizon::Long => {
                t.priority = Priority::P3Background;
                t.deadline = Some(now + Duration::days(14));
                t.deadline_urgency = 3;
            }
        }

        let intents = project_task_reminders(&t, ReminderSource::Lts, now, policy);
        for mut ri in intents {
            if due_now {
                ri.send_at_utc = now;
            }
            if emitted.len() >= limit {
                break;
            }
            emitted.push(QueuedIntent {
                recipient: resolved_to.clone(),
                channel: resolved_channel.clone(),
                intent: ri,
            });
        }
        if emitted.len() >= limit {
            break;
        }
    }

    let q = queue_path()?;
    if let Some(parent) = q.parent() {
        fs::create_dir_all(parent).with_context(|| format!("create {}", parent.display()))?;
    }

    let mut f = OpenOptions::new().create(true).append(true).open(&q)?;
    for e in &emitted {
        let line = serde_json::to_string(e)?;
        writeln!(f, "{}", line)?;
    }

    println!("Queued {} reminder intents in {}", emitted.len(), q.display());
    Ok(())
}

fn list(limit: usize) -> Result<()> {
    let q = queue_path()?;
    if !q.exists() {
        println!("No reminder queue at {}", q.display());
        return Ok(());
    }

    let f = fs::File::open(&q)?;
    let reader = BufReader::new(f);

    let mut rows: Vec<QueuedIntent> = Vec::new();
    for line in reader.lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        if let Ok(v) = serde_json::from_str::<QueuedIntent>(&line) {
            rows.push(v);
        }
    }

    let take = rows.len().min(limit);
    for (i, r) in rows.iter().rev().take(take).enumerate() {
        println!(
            "{}. [{}] {} -> {} at {}",
            i + 1,
            r.channel,
            r.intent.title,
            r.recipient,
            r.intent.send_at_utc.to_rfc3339()
        );
    }

    Ok(())
}

fn dispatch(dry_run: bool, limit: Option<usize>, include_future_minutes: Option<i64>) -> Result<()> {
    let cfg = load_config()?;
    let resolved_limit = limit.unwrap_or(cfg.reminders.max_dispatch_per_run);
    let future_min = include_future_minutes.unwrap_or(cfg.reminders.include_future_minutes_default);

    let q = queue_path()?;
    if !q.exists() {
        println!("No reminder queue at {}", q.display());
        return Ok(());
    }

    let sk = sent_keys_path()?;
    if let Some(parent) = sk.parent() {
        fs::create_dir_all(parent).with_context(|| format!("create {}", parent.display()))?;
    }

    let sent_keys: HashSet<String> = if sk.exists() {
        let f = fs::File::open(&sk)?;
        BufReader::new(f)
            .lines()
            .filter_map(|l| l.ok())
            .collect::<HashSet<_>>()
    } else {
        HashSet::new()
    };

    let f = fs::File::open(&q)?;
    let reader = BufReader::new(f);

    let now = Utc::now();
    let due_cutoff = now + Duration::minutes(future_min.max(0));
    let mut due: Vec<QueuedIntent> = Vec::new();

    for line in reader.lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        if let Ok(v) = serde_json::from_str::<QueuedIntent>(&line) {
            if v.intent.send_at_utc <= due_cutoff && !sent_keys.contains(&v.intent.dedupe_key) {
                due.push(v);
            }
        }
    }

    if due.is_empty() {
        println!("No due unsent reminders.");
        return Ok(());
    }

    let mut sent_now = 0usize;
    let mut sent_log = OpenOptions::new().create(true).append(true).open(&sk)?;

    for item in due.into_iter().take(resolved_limit) {
        if dry_run {
            println!(
                "[DRY RUN] would send [{}] {} -> {}",
                item.channel, item.intent.title, item.recipient
            );
            continue;
        }

        match item.channel.as_str() {
            "imessage" => {
                let text = format!("{}\n{}", item.intent.title, item.intent.body);
                send_imessage(&item.recipient, &text)?;
                maybe_log_sent_to_google_calendar(&item)?;
                writeln!(sent_log, "{}", item.intent.dedupe_key)?;
                sent_now += 1;
            }
            other => {
                println!("Skipping unsupported channel: {other}");
            }
        }
    }

    println!("Dispatch complete. Sent {} reminders.", sent_now);
    Ok(())
}

fn status() -> Result<()> {
    let q = queue_path()?;
    let sk = sent_keys_path()?;

    let sent_keys: HashSet<String> = if sk.exists() {
        let f = fs::File::open(&sk)?;
        BufReader::new(f)
            .lines()
            .filter_map(|l| l.ok())
            .collect::<HashSet<_>>()
    } else {
        HashSet::new()
    };

    if !q.exists() {
        println!("Queue: 0 total, 0 due, 0 future, {} sent", sent_keys.len());
        return Ok(());
    }

    let now = Utc::now();
    let f = fs::File::open(&q)?;
    let reader = BufReader::new(f);

    let mut total = 0usize;
    let mut due = 0usize;
    let mut future = 0usize;
    let mut already_sent = 0usize;

    for line in reader.lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        if let Ok(v) = serde_json::from_str::<QueuedIntent>(&line) {
            total += 1;
            if sent_keys.contains(&v.intent.dedupe_key) {
                already_sent += 1;
            } else if v.intent.send_at_utc <= now {
                due += 1;
            } else {
                future += 1;
            }
        }
    }

    println!(
        "Queue: {} total, {} due, {} future, {} sent",
        total, due, future, already_sent
    );
    Ok(())
}

fn config_check() -> Result<()> {
    let cfg = load_config()?;

    println!("Reminder config:\n");
    println!("- default_channel: {}", cfg.reminders.default_channel);
    println!(
        "- default_recipient: {}",
        cfg.reminders
            .default_recipient
            .as_deref()
            .unwrap_or("<not set>")
    );
    println!("- max_dispatch_per_run: {}", cfg.reminders.max_dispatch_per_run);
    println!(
        "- include_future_minutes_default: {}",
        cfg.reminders.include_future_minutes_default
    );
    println!(
        "- google_calendar_log_enabled: {}",
        cfg.reminders.google_calendar_log_enabled
    );
    println!(
        "- google_calendar_id: {}",
        cfg.reminders
            .google_calendar_id
            .as_deref()
            .unwrap_or("primary")
    );

    if cfg.reminders.default_recipient.is_none() {
        println!("\nWhat to configure next:");
        println!("Set ~/.rewind/config.toml:");
        println!("[reminders]");
        println!("default_channel = \"imessage\"");
        println!("default_recipient = \"+17373151963\"");
        println!("max_dispatch_per_run = 10");
        println!("include_future_minutes_default = 0");
        println!("google_calendar_log_enabled = true");
        println!("google_calendar_id = \"primary\"");
    }

    Ok(())
}

fn maybe_log_sent_to_google_calendar(item: &QueuedIntent) -> Result<()> {
    let cfg = load_config()?;
    if !cfg.reminders.google_calendar_log_enabled {
        return Ok(());
    }

    let calendar = cfg
        .reminders
        .google_calendar_id
        .as_deref()
        .unwrap_or("primary");

    let gcal = match which::which("gcalcli") {
        Ok(p) => p,
        Err(_) => {
            println!("gcalcli not found; skipping calendar reminder log");
            return Ok(());
        }
    };

    let when = Utc::now().format("%Y-%m-%d %H:%M").to_string();
    let title = format!("Missed reminder log: {}", item.intent.task_id);
    let desc = format!(
        "Sent reminder via {} to {}.\\nTitle: {}\\nDedupe: {}",
        item.channel, item.recipient, item.intent.title, item.intent.dedupe_key
    );

    let output = std::process::Command::new(gcal)
        .arg("add")
        .args(["--calendar", calendar])
        .args(["--title", &title])
        .args(["--when", &when])
        .args(["--duration", "5"])
        .args(["--description", &desc])
        .arg("--noprompt")
        .output()
        .context("running gcalcli add")?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        println!("Failed to log reminder in calendar: {stderr}");
    }

    Ok(())
}

fn send_imessage(to: &str, text: &str) -> Result<()> {
    if !cfg!(target_os = "macos") {
        anyhow::bail!("iMessage delivery is macOS-only");
    }

    if !is_valid_imessage_target(to) {
        anyhow::bail!(
            "Invalid iMessage target: must be E.164 phone (+1234567890) or email user@example.com"
        );
    }

    let escaped_to = escape_applescript(to);
    let escaped_text = escape_applescript(text);

    let script = format!(
        r#"tell application "Messages"
    set targetService to 1st account whose service type = iMessage
    set targetBuddy to participant "{escaped_to}" of targetService
    send "{escaped_text}" to targetBuddy
end tell"#
    );

    let output = std::process::Command::new("osascript")
        .arg("-e")
        .arg(&script)
        .output()
        .context("running osascript")?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        anyhow::bail!("iMessage send failed: {stderr}");
    }

    println!("Sent iMessage to {to}");
    Ok(())
}

fn escape_applescript(s: &str) -> String {
    s.replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
}

fn is_valid_imessage_target(target: &str) -> bool {
    let target = target.trim();
    if target.is_empty() {
        return false;
    }

    if target.starts_with('+') {
        let digits: String = target.chars().filter(char::is_ascii_digit).collect();
        return (7..=15).contains(&digits.len());
    }

    if let Some(at) = target.find('@') {
        let local = &target[..at];
        let domain = &target[at + 1..];
        let local_ok =
            !local.is_empty() && local.chars().all(|c| c.is_alphanumeric() || "._+-".contains(c));
        let domain_ok = !domain.is_empty()
            && domain.contains('.')
            && domain
                .chars()
                .all(|c| c.is_alphanumeric() || c == '-' || c == '.');
        return local_ok && domain_ok;
    }

    false
}
