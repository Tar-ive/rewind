//! Short-Term Scheduler (STS) — modified MLFQ priority queues.
//!
//! Port target: `backend/src/engine/sts.py` (origin/main).

use crate::task::{Priority, Task, TaskStatus};
use chrono::{DateTime, Utc};
use std::cmp::Ordering;
use std::collections::BinaryHeap;

#[derive(Debug, Clone)]
struct QueueEntry {
    // Lower sort_key = higher priority within a given priority queue.
    // We use -deadline_urgency so bigger urgency comes first.
    sort_key: i32,
    seq: u64,
    task: Task,
}

impl PartialEq for QueueEntry {
    fn eq(&self, other: &Self) -> bool {
        self.sort_key == other.sort_key && self.seq == other.seq
    }
}
impl Eq for QueueEntry {}

impl PartialOrd for QueueEntry {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for QueueEntry {
    fn cmp(&self, other: &Self) -> Ordering {
        // BinaryHeap is max-heap.
        // We want the smallest sort_key first, then smallest seq.
        // So we invert ordering.
        other
            .sort_key
            .cmp(&self.sort_key)
            .then_with(|| other.seq.cmp(&self.seq))
    }
}

#[derive(Debug, Default)]
pub struct ShortTermScheduler {
    queues: [BinaryHeap<QueueEntry>; 4],
    current_task: Option<Task>,
    delegation_queue: Vec<Task>,
    seq: u64,
}

impl ShortTermScheduler {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn enqueue(&mut self, mut task: Task, now: DateTime<Utc>) {
        let p = self.classify_priority(&task, now);
        task.priority = p;

        let idx = priority_index(p);
        let sort_key = -task.deadline_urgency;

        self.seq += 1;
        self.queues[idx].push(QueueEntry {
            sort_key,
            seq: self.seq,
            task,
        });
    }

    pub fn enqueue_batch(&mut self, tasks: Vec<Task>, now: DateTime<Utc>) {
        for t in tasks {
            self.enqueue(t, now);
        }
    }

    /// Dequeue next runnable task respecting energy constraints.
    pub fn dequeue(&mut self, energy_level: i32) -> Option<Task> {
        for p in [Priority::P0Urgent, Priority::P1Important, Priority::P2Normal, Priority::P3Background] {
            let idx = priority_index(p);

            // Pop until we find an energy-compatible task, buffering skipped.
            let mut skipped: Vec<QueueEntry> = Vec::new();
            let mut result: Option<Task> = None;

            while let Some(entry) = self.queues[idx].pop() {
                if entry.task.energy_cost <= energy_level {
                    result = Some(entry.task);
                    break;
                }
                skipped.push(entry);
            }

            // Put skipped entries back.
            for e in skipped {
                self.queues[idx].push(e);
            }

            if result.is_some() {
                return result;
            }
        }

        None
    }

    pub fn set_current(&mut self, mut task: Task) {
        task.status = TaskStatus::InProgress;
        self.current_task = Some(task);
    }

    pub fn clear_current(&mut self) {
        self.current_task = None;
    }

    pub fn get_current(&self) -> Option<&Task> {
        self.current_task.as_ref()
    }

    /// Delegate all P3 tasks when energy is low.
    pub fn auto_delegate_p3(&mut self, energy_level: i32) -> Vec<Task> {
        if energy_level > 2 {
            return Vec::new();
        }

        let idx = priority_index(Priority::P3Background);
        let mut delegated = Vec::new();
        while let Some(mut entry) = self.queues[idx].pop() {
            entry.task.status = TaskStatus::Delegated;
            delegated.push(entry.task.clone());
            self.delegation_queue.push(entry.task);
        }
        delegated
    }

    pub fn delegation_queue(&mut self) -> Vec<Task> {
        let q = self.delegation_queue.clone();
        self.delegation_queue.clear();
        q
    }

    pub fn total_count(&self) -> usize {
        self.queues.iter().map(|q| q.len()).sum()
    }

    fn classify_priority(&self, task: &Task, now: DateTime<Utc>) -> Priority {
        // Respect manually set priority if not default.
        if task.priority != Priority::P2Normal {
            return task.priority;
        }

        if let Some(dl) = task.deadline {
            let secs_left = (dl - now).num_seconds();
            let hours_left = (secs_left as f64) / 3600.0;
            if hours_left <= 2.0 {
                return Priority::P0Urgent;
            }
            if hours_left <= 24.0 {
                return Priority::P1Important;
            }
        }

        if task.cognitive_load <= 1 && task.energy_cost <= 1 {
            return Priority::P3Background;
        }

        Priority::P2Normal
    }
}

fn priority_index(p: Priority) -> usize {
    match p {
        Priority::P0Urgent => 0,
        Priority::P1Important => 1,
        Priority::P2Normal => 2,
        Priority::P3Background => 3,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::task::Task;
    use chrono::Duration;

    #[test]
    fn test_priority_by_deadline_2h() {
        let now = Utc::now();
        let t = Task::new("t1", "due soon")
            .with_deadline(now + Duration::minutes(90))
            .with_deadline_urgency(10);

        let mut sts = ShortTermScheduler::new();
        sts.enqueue(t, now);
        assert_eq!(sts.total_count(), 1);

        let next = sts.dequeue(5).unwrap();
        assert_eq!(next.priority, Priority::P0Urgent);
    }

    #[test]
    fn test_priority_by_deadline_24h() {
        let now = Utc::now();
        let t = Task::new("t1", "due today")
            .with_deadline(now + Duration::hours(10))
            .with_deadline_urgency(7);

        let mut sts = ShortTermScheduler::new();
        sts.enqueue(t, now);
        let next = sts.dequeue(5).unwrap();
        assert_eq!(next.priority, Priority::P1Important);
    }

    #[test]
    fn test_energy_constraint_skips_high_energy() {
        let now = Utc::now();
        let high = Task::new("t1", "hard").with_energy(5).with_deadline_urgency(10);
        let low = Task::new("t2", "easy").with_energy(1).with_deadline_urgency(1);

        let mut sts = ShortTermScheduler::new();
        sts.enqueue(high, now);
        sts.enqueue(low, now);

        // With energy=1, should skip high-energy task.
        let next = sts.dequeue(1).unwrap();
        assert_eq!(next.id, "t2");
    }

    #[test]
    fn test_auto_delegate_p3() {
        let now = Utc::now();
        let bg = Task::new("t3", "low effort")
            .with_energy(1)
            .with_cognitive(1)
            .with_deadline_urgency(0);

        let mut sts = ShortTermScheduler::new();
        sts.enqueue(bg, now);

        let delegated = sts.auto_delegate_p3(2);
        assert_eq!(delegated.len(), 1);
        assert_eq!(delegated[0].status, TaskStatus::Delegated);
        assert_eq!(sts.total_count(), 0);
    }
}
