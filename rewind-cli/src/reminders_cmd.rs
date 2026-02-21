use anyhow::{Context, Result};
use chrono::{Duration, Utc};
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
    }
}

fn queue_path() -> Result<std::path::PathBuf> {
    Ok(ensure_rewind_home()?.join("reminders").join("intents.jsonl"))
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
