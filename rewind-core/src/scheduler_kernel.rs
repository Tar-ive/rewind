//! Scheduler Kernel — orchestration layer for disruption recovery.
//!
//! Scaffolding aligned to `docs/spec-disruption-recovery-and-ios-bridge.md`.
//!
//! This module wires existing MTS + STS primitives to the disruption event
//! contracts in `crate::disruption`.

use chrono::{DateTime, NaiveDate, Utc};

use crate::disruption::{DelegationItem, DelegationQueue, DisruptionEvent, DisruptionSeverity, UpdatedSchedule};
use crate::mts::{handle_swap_in, handle_swap_out, maybe_delegate_low_energy, SwapResult};
use crate::sts::ShortTermScheduler;
use crate::task::{Task, TaskStatus};

/// Context sentinel emits changes; real adapters are out-of-scope for this scaffold.
///
/// NOTE: `ContextChangeEvent` lives in `crate::disruption`.
pub trait ContextSentinel {
    fn poll(&mut self, now: DateTime<Utc>) -> Vec<crate::disruption::ContextChangeEvent>;
}

/// Disruption detector classifies context changes into disruption events.
pub trait DisruptionDetector {
    fn analyze(&self, event: &crate::disruption::ContextChangeEvent) -> DisruptionEvent;
}

pub trait EnergyProvider {
    /// Return a coarse energy level for scheduling decisions.
    fn energy_level(&self, now: DateTime<Utc>) -> i32;
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ProfileSnapshot {
    /// v0: peak focus windows. Stringly typed as "HH:MM-HH:MM" until formalized.
    pub peak_hours: Vec<String>,
    /// v0: optional map of task_id -> avg duration minutes.
    pub avg_task_durations: Vec<(String, i32)>,
}

pub trait ProfilerProvider {
    fn profile(&self) -> ProfileSnapshot;
}

#[derive(Debug, Clone, PartialEq)]
pub struct KernelOutput {
    pub schedule: UpdatedSchedule,
    pub delegation: DelegationQueue,
    /// MTS swap summary for observability.
    pub mts_summary: String,
}

/// Scheduler Kernel: ties together providers and existing scheduling primitives.
#[derive(Debug, Clone)]
pub struct SchedulerKernel<E: EnergyProvider, P: ProfilerProvider> {
    energy: E,
    profiler: P,
}

impl<E: EnergyProvider, P: ProfilerProvider> SchedulerKernel<E, P> {
    pub fn new(energy: E, profiler: P) -> Self {
        Self { energy, profiler }
    }

    /// Handle a disruption event and produce a new schedule + delegation queue.
    ///
    /// v0 behavior:
    /// - compute energy level
    /// - (placeholder) consult profile snapshot
    /// - run swap-out for major/critical events
    /// - run swap-in for any freed minutes
    /// - produce an ordered task list via STS
    /// - delegate P3 tasks when energy is low
    pub fn handle_disruption(
        &self,
        disruption: DisruptionEvent,
        active_tasks: Vec<Task>,
        backlog_tasks: Vec<Task>,
        now: DateTime<Utc>,
    ) -> KernelOutput {
        let energy_level = self.energy.energy_level(now);
        let _profile = self.profiler.profile();

        // Seed STS with active tasks.
        let mut sts = ShortTermScheduler::new();
        let mut active = active_tasks;
        for t in active.iter_mut() {
            // Kernel assumes these are active unless explicitly set.
            if t.status == TaskStatus::Backlog {
                t.status = TaskStatus::Active;
            }
            sts.enqueue(t.clone(), now);
        }

        // Swap-out minutes are a policy decision; this is a stub that uses cascade_count.
        let cascade = disruption.cascade_count as i32;
        let minutes_needed = match disruption.severity {
            DisruptionSeverity::Minor => 0,
            DisruptionSeverity::Major => cascade.max(1) * 15,
            DisruptionSeverity::Critical => cascade.max(1) * 30,
        };

        let mut mts_summary_parts: Vec<String> = Vec::new();

        let mut swap_out_res = SwapResult::default();
        let freed_minutes = if minutes_needed > 0 {
            swap_out_res = handle_swap_out(minutes_needed, &mut active);
            mts_summary_parts.push(swap_out_res.summary.clone());

            swap_out_res
                .swapped_out
                .iter()
                .map(|t| t.estimated_duration)
                .sum::<i32>()
        } else {
            0
        };

        let mut backlog = backlog_tasks;
        let mut swap_in_res = SwapResult::default();
        if freed_minutes > 0 {
            swap_in_res = handle_swap_in(freed_minutes, energy_level, &mut backlog, &mut sts, now);
            mts_summary_parts.push(swap_in_res.summary.clone());
        }

        // If energy is low, delegate P3.
        maybe_delegate_low_energy(&mut sts, energy_level);
        let delegated_tasks = sts.delegation_queue();

        // Produce ordered schedule by dequeuing.
        let mut task_order: Vec<String> = Vec::new();
        while let Some(t) = sts.dequeue(energy_level) {
            task_order.push(t.id);
        }

        let delegation = DelegationQueue {
            items: delegated_tasks
                .into_iter()
                .map(|t| DelegationItem {
                    task_id: t.id,
                    channel: "unknown".to_string(),
                    draft_type: "unknown".to_string(),
                    // v0 mapping: Priority enum is 0..3-ish; keep it simple.
                    priority: match t.priority {
                        crate::task::Priority::P0Urgent => 30,
                        crate::task::Priority::P1Important => 20,
                        crate::task::Priority::P2Normal => 10,
                        crate::task::Priority::P3Background => 1,
                    },
                })
                .collect(),
        };

        let schedule = UpdatedSchedule {
            day: NaiveDate::from_ymd_opt(now.year(), now.month(), now.day()).unwrap_or_else(|| now.date_naive()),
            task_order,
            swapped_out: swap_out_res.swapped_out.into_iter().map(|t| t.id).collect(),
            swapped_in: swap_in_res.swapped_in.into_iter().map(|t| t.id).collect(),
            energy_level,
        };

        KernelOutput {
            schedule,
            delegation,
            mts_summary: mts_summary_parts.join("; "),
        }
    }
}

// chrono helpers without pulling in chrono::Datelike in every file.
trait DateParts {
    fn year(&self) -> i32;
    fn month(&self) -> u32;
    fn day(&self) -> u32;
}
impl DateParts for DateTime<Utc> {
    fn year(&self) -> i32 {
        use chrono::Datelike;
        self.date_naive().year()
    }
    fn month(&self) -> u32 {
        use chrono::Datelike;
        self.date_naive().month()
    }
    fn day(&self) -> u32 {
        use chrono::Datelike;
        self.date_naive().day()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    #[derive(Debug, Clone)]
    struct FixedEnergy(i32);
    impl EnergyProvider for FixedEnergy {
        fn energy_level(&self, _now: DateTime<Utc>) -> i32 {
            self.0
        }
    }

    #[derive(Debug, Clone, Default)]
    struct FixedProfiler;
    impl ProfilerProvider for FixedProfiler {
        fn profile(&self) -> ProfileSnapshot {
            ProfileSnapshot {
                peak_hours: vec!["09:00-11:00".to_string()],
                avg_task_durations: vec![],
            }
        }
    }

    fn disruption(severity: DisruptionSeverity, cascade_count: u32, now: DateTime<Utc>) -> DisruptionEvent {
        DisruptionEvent {
            severity,
            cascade_count,
            reason: "test".to_string(),
            context_event_id: "evt_001".to_string(),
            timestamp_utc: now,
        }
    }

    #[test]
    fn kernel_minor_disruption_no_swaps_orders_tasks() {
        let kernel = SchedulerKernel::new(FixedEnergy(5), FixedProfiler);
        let now = Utc.with_ymd_and_hms(2026, 2, 21, 8, 25, 0).unwrap();

        let active = vec![
            Task::new("a1", "important").with_deadline_urgency(8).with_duration(30),
            Task::new("a2", "less").with_deadline_urgency(2).with_duration(30),
        ];

        let out = kernel.handle_disruption(disruption(DisruptionSeverity::Minor, 0, now), active, vec![], now);

        assert!(out.schedule.swapped_out.is_empty());
        assert!(out.schedule.swapped_in.is_empty());
        assert!(out.delegation.items.is_empty());
        assert_eq!(out.schedule.task_order, vec!["a1".to_string(), "a2".to_string()]);
    }

    #[test]
    fn kernel_major_disruption_swaps_out_and_in() {
        let kernel = SchedulerKernel::new(FixedEnergy(5), FixedProfiler);
        let now = Utc.with_ymd_and_hms(2026, 2, 21, 8, 25, 0).unwrap();

        let mut bg = Task::new("a_bg", "background")
            .with_deadline_urgency(0)
            .with_duration(30)
            .with_energy(1)
            .with_cognitive(1);
        bg.priority = crate::task::Priority::P3Background;
        bg.status = TaskStatus::Active;

        let mut imp = Task::new("a_imp", "important")
            .with_deadline_urgency(9)
            .with_duration(30)
            .with_energy(3)
            .with_cognitive(4);
        imp.priority = crate::task::Priority::P1Important;
        imp.status = TaskStatus::Active;

        let backlog = vec![Task::new("b1", "backlog")
            .with_duration(30)
            .with_deadline_urgency(7)
            .with_energy(1)
            .with_cognitive(1)];

        let out = kernel.handle_disruption(disruption(DisruptionSeverity::Major, 1, now), vec![bg, imp], backlog, now);

        assert!(!out.schedule.swapped_out.is_empty());
        assert!(!out.schedule.swapped_in.is_empty());
        assert!(out.mts_summary.contains("swap-out"));
        assert!(out.mts_summary.contains("swap-in"));
    }

    #[test]
    fn kernel_low_energy_delegates_p3() {
        let kernel = SchedulerKernel::new(FixedEnergy(2), FixedProfiler);
        let now = Utc.with_ymd_and_hms(2026, 2, 21, 8, 25, 0).unwrap();

        let bg = Task::new("a_bg", "background")
            .with_deadline_urgency(0)
            .with_duration(15)
            .with_energy(1)
            .with_cognitive(1);

        let out = kernel.handle_disruption(disruption(DisruptionSeverity::Minor, 0, now), vec![bg], vec![], now);

        assert_eq!(out.delegation.items.len(), 1);
        assert_eq!(out.delegation.items[0].task_id, "a_bg");
    }
}
