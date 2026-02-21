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

use crate::state::{ensure_rewind_home, goals_path};

#[derive(Subcommand, Debug)]
pub enum RemindersCommand {
    /// Build reminder intents from goals and append to local queue
    Plan {
        /// Delivery target (phone/email)
        #[arg(long)]
        to: String,

        /// Channel label (default: imessage)
        #[arg(long, default_value = "imessage")]
        channel: String,

        /// Max reminders to generate
        #[arg(long, default_value_t = 10)]
        limit: usize,
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

        /// Max sends in one run
        #[arg(long, default_value_t = 10)]
        limit: usize,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct QueuedIntent {
    recipient: String,
    channel: String,
    intent: ReminderIntent,
}

pub fn run(cmd: RemindersCommand) -> Result<()> {
    match cmd {
        RemindersCommand::Plan { to, channel, limit } => plan(&to, &channel, limit),
        RemindersCommand::List { limit } => list(limit),
        RemindersCommand::SendImessage { to, text } => send_imessage(&to, &text),
        RemindersCommand::Dispatch { dry_run, limit } => dispatch(dry_run, limit),
    }
}

fn queue_path() -> Result<std::path::PathBuf> {
    Ok(ensure_rewind_home()?.join("reminders").join("intents.jsonl"))
}

fn sent_keys_path() -> Result<std::path::PathBuf> {
    Ok(ensure_rewind_home()?.join("reminders").join("sent_keys.txt"))
}

fn plan(to: &str, channel: &str, limit: usize) -> Result<()> {
    let gp = goals_path()?;
    let md = fs::read_to_string(&gp).with_context(|| format!("read {}", gp.display()))?;
    let goals = parse_goals_md(&md);

    if goals.is_empty() {
        anyhow::bail!("no goals found in {}", gp.display());
    }

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
        for ri in intents {
            if emitted.len() >= limit {
                break;
            }
            emitted.push(QueuedIntent {
                recipient: to.to_string(),
                channel: channel.to_string(),
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

fn dispatch(dry_run: bool, limit: usize) -> Result<()> {
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
    let mut due: Vec<QueuedIntent> = Vec::new();

    for line in reader.lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        if let Ok(v) = serde_json::from_str::<QueuedIntent>(&line) {
            if v.intent.send_at_utc <= now && !sent_keys.contains(&v.intent.dedupe_key) {
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

    for item in due.into_iter().take(limit) {
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
