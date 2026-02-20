//! TaskBuffer — deterministic, bucketed backlog storage.
//!
//! Purpose:
//! - Replace a raw Vec<Task> backlog with a structure that can quickly provide
//!   "swap-in" candidates for MTS (and later LTS).
//! - Stay fully deterministic: no LLM, no randomness.
//!
//! Design (v0):
//! - Keep canonical Task copies in a map (id -> Task).
//! - Maintain bucket indexes for quick candidate enumeration.
//!   Buckets are coarse, because we care about predictable behavior more than
//!   micro-optimizing.
//!
//! Buckets:
//! - energy_cost: 1..=5
//! - duration_bin: <=15, <=30, <=60, >60
//!
//! Candidate ranking (same as MTS swap-in):
//! - deadline_urgency DESC
//! - priority ASC (P0 best)
//! - duration ASC (fit smaller tasks first when tied)

use crate::task::{Priority, Task, TaskStatus};
use anyhow::{bail, Result};
use std::collections::{HashMap, HashSet};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
enum DurationBin {
    Le15,
    Le30,
    Le60,
    Gt60,
}

fn duration_bin(minutes: i32) -> DurationBin {
    match minutes {
        m if m <= 15 => DurationBin::Le15,
        m if m <= 30 => DurationBin::Le30,
        m if m <= 60 => DurationBin::Le60,
        _ => DurationBin::Gt60,
    }
}

#[derive(Debug, Default, Clone)]
pub struct TaskBuffer {
    tasks: HashMap<String, Task>,

    // index[energy_cost][duration_bin] = set(task_id)
    idx: HashMap<(i32, DurationBin), HashSet<String>>,
}

impl TaskBuffer {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn len(&self) -> usize {
        self.tasks.len()
    }

    pub fn is_empty(&self) -> bool {
        self.tasks.is_empty()
    }

    pub fn get(&self, id: &str) -> Option<&Task> {
        self.tasks.get(id)
    }

    pub fn upsert(&mut self, task: Task) {
        // remove prior index
        if let Some(old) = self.tasks.get(&task.id).cloned() {
            self.deindex(&old);
        }
        self.index(&task);
        self.tasks.insert(task.id.clone(), task);
    }

    pub fn remove(&mut self, id: &str) -> Option<Task> {
        let t = self.tasks.remove(id);
        if let Some(ref task) = t {
            self.deindex(task);
        }
        t
    }

    /// Select tasks to swap-in, removing them from the buffer.
    ///
    /// Greedy fill algorithm:
    /// - repeatedly pick the best remaining candidate that fits within remaining minutes.
    pub fn take_swap_in(
        &mut self,
        freed_minutes: i32,
        energy_level: i32,
    ) -> Result<Vec<Task>> {
        if freed_minutes <= 0 {
            return Ok(vec![]);
        }
        if !(1..=5).contains(&energy_level) {
            bail!("energy_level must be 1..=5");
        }

        let mut remaining = freed_minutes;
        let mut out = Vec::new();

        loop {
            let best = self.best_candidate(remaining, energy_level);
            let Some(id) = best else { break };

            let mut t = self
                .remove(&id)
                .expect("candidate id must exist")
                .clone();

            // Only backlog tasks can be swapped in.
            if t.status != TaskStatus::Backlog {
                // Put it back and stop (shouldn't happen under correct indexing).
                self.upsert(t);
                break;
            }

            remaining -= t.estimated_duration;
            t.status = TaskStatus::Active;
            out.push(t);

            if remaining <= 0 {
                break;
            }
        }

        Ok(out)
    }

    fn index(&mut self, task: &Task) {
        let key = (task.energy_cost, duration_bin(task.estimated_duration));
        self.idx
            .entry(key)
            .or_default()
            .insert(task.id.clone());
    }

    fn deindex(&mut self, task: &Task) {
        let key = (task.energy_cost, duration_bin(task.estimated_duration));
        if let Some(set) = self.idx.get_mut(&key) {
            set.remove(&task.id);
            if set.is_empty() {
                self.idx.remove(&key);
            }
        }
    }

    fn best_candidate(&self, remaining: i32, energy_level: i32) -> Option<String> {
        // Enumerate buckets in an order that tends to fit tasks quickly.
        // Energy: 1..=energy_level
        // Duration bins: small -> large
        let duration_bins = [DurationBin::Le15, DurationBin::Le30, DurationBin::Le60, DurationBin::Gt60];

        let mut best: Option<(&Task, i32, Priority)> = None;

        for e in 1..=energy_level {
            for bin in duration_bins {
                let key = (e, bin);
                let Some(set) = self.idx.get(&key) else { continue };

                for id in set {
                    let Some(t) = self.tasks.get(id) else { continue };
                    if t.status != TaskStatus::Backlog {
                        continue;
                    }
                    if t.energy_cost > energy_level {
                        continue;
                    }
                    if t.estimated_duration > remaining {
                        continue;
                    }

                    let cand = (t, t.deadline_urgency, t.priority);

                    best = match best {
                        None => Some(cand),
                        Some((bt, bu, bp)) => {
                            // urgency desc
                            if cand.1 > bu {
                                Some(cand)
                            } else if cand.1 < bu {
                                Some((bt, bu, bp))
                            } else {
                                // priority asc
                                if cand.2 < bp {
                                    Some(cand)
                                } else if cand.2 > bp {
                                    Some((bt, bu, bp))
                                } else {
                                    // duration asc
                                    if t.estimated_duration < bt.estimated_duration {
                                        Some(cand)
                                    } else {
                                        Some((bt, bu, bp))
                                    }
                                }
                            }
                        }
                    };
                }
            }
        }

        best.map(|(t, _, _)| t.id.clone())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn takes_high_urgency_first_and_removes_from_buffer() {
        let mut b = TaskBuffer::new();
        b.upsert(Task::new("t1", "low").with_duration(30).with_energy(3).with_deadline_urgency(1));
        b.upsert(Task::new("t2", "high").with_duration(30).with_energy(3).with_deadline_urgency(9));

        let picked = b.take_swap_in(30, 5).unwrap();
        assert_eq!(picked.len(), 1);
        assert_eq!(picked[0].id, "t2");
        assert!(b.get("t2").is_none());
        assert!(b.get("t1").is_some());
    }

    #[test]
    fn respects_remaining_minutes_and_energy() {
        let mut b = TaskBuffer::new();
        b.upsert(Task::new("a", "big").with_duration(60).with_energy(5).with_deadline_urgency(10));
        b.upsert(Task::new("b", "small").with_duration(15).with_energy(2).with_deadline_urgency(5));

        // not enough time for big
        let picked = b.take_swap_in(30, 5).unwrap();
        assert_eq!(picked.len(), 1);
        assert_eq!(picked[0].id, "b");

        // energy too low for big
        let picked2 = b.take_swap_in(90, 2).unwrap();
        assert_eq!(picked2.len(), 0);
        assert!(b.get("a").is_some());
    }
}
