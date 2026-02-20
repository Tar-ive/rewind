//! Medium-Term Scheduler (MTS) — swap engine.
//!
//! Port target: `backend/src/engine/mts.py` (origin/main).
//!
//! In Rust, we keep MTS pure + file-backed. Storage backends (redis/sqlite) come later.

use crate::sts::ShortTermScheduler;
use crate::task::{Priority, Task, TaskStatus};

#[derive(Debug, Clone, Default, PartialEq)]
pub struct SwapResult {
    pub swapped_in: Vec<Task>,
    pub swapped_out: Vec<Task>,
    pub delegated: Vec<Task>,
    pub summary: String,
}

/// Swap-in: use freed time to pull tasks from backlog into active schedule.
///
/// Algorithm (deterministic):
/// 1) filter backlog tasks by duration <= remaining_minutes
/// 2) filter by energy_cost <= energy_level
/// 3) rank by deadline_urgency DESC then priority ASC (P0 best)
/// 4) activate + enqueue into STS
pub fn handle_swap_in(
    freed_minutes: i32,
    energy_level: i32,
    backlog: &mut Vec<Task>,
    sts: &mut ShortTermScheduler,
    now: chrono::DateTime<chrono::Utc>,
) -> SwapResult {
    let mut remaining = freed_minutes;
    let mut swapped_in = Vec::new();

    // rank candidates
    let mut candidates: Vec<(usize, i32, Priority)> = backlog
        .iter()
        .enumerate()
        .filter(|(_, t)| t.status == TaskStatus::Backlog)
        .filter(|(_, t)| t.estimated_duration <= remaining)
        .filter(|(_, t)| t.energy_cost <= energy_level)
        .map(|(i, t)| (i, t.deadline_urgency, t.priority))
        .collect();

    candidates.sort_by(|a, b| {
        // urgency desc
        b.1.cmp(&a.1)
            // then priority asc (P0 best)
            .then_with(|| a.2.cmp(&b.2))
    });

    // We'll remove from backlog by marking and later retaining.
    let mut taken = vec![false; backlog.len()];

    for (idx, _, _) in candidates {
        if taken[idx] {
            continue;
        }
        let t = &backlog[idx];
        if t.estimated_duration > remaining {
            continue;
        }

        let mut task = backlog[idx].clone();
        task.status = TaskStatus::Active;

        remaining -= task.estimated_duration;
        sts.enqueue(task.clone(), now);
        swapped_in.push(task);
        taken[idx] = true;

        if remaining <= 0 {
            break;
        }
    }

    // Drop taken tasks from backlog
    let mut new_backlog = Vec::new();
    for (i, t) in backlog.drain(..).enumerate() {
        if !taken[i] {
            new_backlog.push(t);
        }
    }
    *backlog = new_backlog;

    let used = freed_minutes - remaining;
    let summary = format!(
        "swap-in: added {} tasks using {} of {} minutes",
        swapped_in.len(),
        used,
        freed_minutes
    );

    SwapResult {
        swapped_in,
        swapped_out: vec![],
        delegated: vec![],
        summary,
    }
}

/// Swap-out: remove low-priority tasks from active schedule to free time.
///
/// Selection: P3 → P2 → P1 → P0; within priority, lowest urgency first.
///
/// Notes:
/// - We do not touch the current in-progress task here (leave to disruption/preemption logic).
pub fn handle_swap_out(
    minutes_needed: i32,
    active: &mut Vec<Task>,
) -> SwapResult {
    let mut candidates: Vec<(usize, Priority, i32, i32)> = active
        .iter()
        .enumerate()
        .filter(|(_, t)| t.status == TaskStatus::Active)
        .map(|(i, t)| (i, t.priority, t.deadline_urgency, t.estimated_duration))
        .collect();

    candidates.sort_by(|a, b| {
        // Priority: P3 first (largest enum value)
        b.1.cmp(&a.1)
            // then least urgent first
            .then_with(|| a.2.cmp(&b.2))
    });

    let mut freed = 0;
    let mut swapped_out = Vec::new();
    let mut take = vec![false; active.len()];

    for (idx, _, _, dur) in candidates {
        if freed >= minutes_needed {
            break;
        }
        freed += dur;
        take[idx] = true;
    }

    for (i, t) in active.iter_mut().enumerate() {
        if take[i] {
            t.status = TaskStatus::SwappedOut;
            swapped_out.push(t.clone());
        }
    }

    let summary = format!(
        "swap-out: swapped out {} tasks freeing {} minutes (needed {})",
        swapped_out.len(),
        freed,
        minutes_needed
    );

    SwapResult {
        swapped_in: vec![],
        swapped_out,
        delegated: vec![],
        summary,
    }
}

/// Delegate: when energy is low, delegate background tasks (P3) from STS.
///
/// This mirrors the Python behavior where STS can delegate P3 tasks when energy <= 2.
pub fn maybe_delegate_low_energy(sts: &mut ShortTermScheduler, energy_level: i32) -> Vec<Task> {
    sts.auto_delegate_p3(energy_level)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::task::{Priority, Task};
    use chrono::{Duration, Utc};

    #[test]
    fn test_swap_in_picks_high_urgency_first() {
        let now = Utc::now();
        let mut backlog = vec![
            Task::new("t1", "low").with_duration(30).with_deadline_urgency(1),
            Task::new("t2", "high").with_duration(30).with_deadline_urgency(9),
        ];
        let mut sts = ShortTermScheduler::new();

        let res = handle_swap_in(30, 5, &mut backlog, &mut sts, now);
        assert_eq!(res.swapped_in.len(), 1);
        assert_eq!(res.swapped_in[0].id, "t2");
        assert_eq!(backlog.len(), 1);
    }

    #[test]
    fn test_swap_out_drops_p3_first() {
        let mut active = vec![
            Task::new("a1", "bg")
                .with_duration(30)
                .with_deadline_urgency(0)
                .with_energy(1)
                .with_cognitive(1),
            Task::new("a2", "important")
                .with_duration(30)
                .with_deadline_urgency(8)
                .with_energy(3)
                .with_cognitive(4)
                .with_deadline(Utc::now() + Duration::hours(2)),
        ];

        // Force statuses/priorities as if they were active.
        active[0].status = TaskStatus::Active;
        active[0].priority = Priority::P3Background;
        active[1].status = TaskStatus::Active;
        active[1].priority = Priority::P1Important;

        let res = handle_swap_out(25, &mut active);
        assert_eq!(res.swapped_out.len(), 1);
        assert_eq!(res.swapped_out[0].id, "a1");
        assert_eq!(active[0].status, TaskStatus::SwappedOut);
        assert_eq!(active[1].status, TaskStatus::Active);
    }
}
