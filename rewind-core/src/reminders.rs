//! Reminder policy + projection primitives for Rewind-native delivery.

use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};

use crate::{Priority, Task, TaskStatus};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum ReminderSource {
    Lts,
    Mts,
    Sts,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReminderIntent {
    pub intent_id: String,
    pub task_id: String,
    pub source: ReminderSource,
    pub title: String,
    pub body: String,
    pub send_at_utc: DateTime<Utc>,
    pub dedupe_key: String,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct ReminderPolicy {
    pub max_per_task: usize,
    pub short_lead_hours: i64,
    pub urgent_lead_minutes: i64,
}

impl Default for ReminderPolicy {
    fn default() -> Self {
        Self {
            max_per_task: 2,
            short_lead_hours: 2,
            urgent_lead_minutes: 15,
        }
    }
}

/// Deterministically project a task into reminder intents.
pub fn project_task_reminders(
    task: &Task,
    source: ReminderSource,
    now: DateTime<Utc>,
    policy: ReminderPolicy,
) -> Vec<ReminderIntent> {
    if task.status == TaskStatus::Completed {
        return vec![];
    }

    let mut out = Vec::new();
    let deadline = task.deadline.unwrap_or(now + Duration::hours(24));

    let title = format!("Reminder: {}", task.title);
    let body = format!("Task {} is due soon (urgency {}).", task.id, task.deadline_urgency);

    let mut slots = Vec::new();

    match task.priority {
        Priority::P0Urgent => {
            slots.push(deadline - Duration::minutes(policy.urgent_lead_minutes));
            slots.push(deadline - Duration::hours(1));
        }
        Priority::P1Important => {
            slots.push(deadline - Duration::hours(policy.short_lead_hours));
            slots.push(deadline - Duration::minutes(policy.urgent_lead_minutes));
        }
        _ => {
            slots.push(deadline - Duration::hours(24));
        }
    }

    for (i, send_at) in slots.into_iter().take(policy.max_per_task).enumerate() {
        if send_at <= now {
            continue;
        }
        // Dedupe should be unique per concrete send slot, not per-day.
        // This keeps repeated same-day plans from over-deduping and dropping legitimate sends.
        let dedupe_key = format!(
            "{}:{}:{}",
            task.id,
            send_at.timestamp(),
            i
        );
        out.push(ReminderIntent {
            intent_id: format!("ri-{}-{}", task.id, i),
            task_id: task.id.clone(),
            source: source.clone(),
            title: title.clone(),
            body: body.clone(),
            send_at_utc: send_at,
            dedupe_key,
        });
    }

    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn completed_task_emits_none() {
        let mut t = Task::new("t1", "done");
        t.status = TaskStatus::Completed;
        let out = project_task_reminders(&t, ReminderSource::Sts, Utc::now(), ReminderPolicy::default());
        assert!(out.is_empty());
    }

    #[test]
    fn urgent_task_emits_two() {
        let now = Utc::now();
        let mut t = Task::new("t2", "urgent").with_deadline(now + Duration::hours(6));
        t.priority = Priority::P0Urgent;
        let out = project_task_reminders(&t, ReminderSource::Sts, now, ReminderPolicy::default());
        assert_eq!(out.len(), 2);
    }
}
