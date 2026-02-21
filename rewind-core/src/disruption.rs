//! Disruption recovery event contracts.
//!
//! These are v0 wire types for the evented disruption pipeline described in
//! `docs/spec-disruption-recovery-and-ios-bridge.md`.
//!
//! Design goals:
//! - serde-ready for JSON transport (iOS bridge, websocket, persistence)
//! - deterministic round-trip behavior
//! - lightweight, no runtime dependencies beyond chrono/serde

use chrono::{DateTime, NaiveDate, Utc};
use serde::{Deserialize, Serialize};

/// Origin of a context delta.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ContextSource {
    Calendar,
    Gmail,
    Slack,
}

/// A raw context delta emitted by a sentinel (calendar/gmail/slack).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ContextChangeEvent {
    pub source: ContextSource,
    /// Free-form change classifier (e.g. "meeting_extended", "new_email_thread").
    pub change_type: String,
    /// Signed delta in minutes (e.g. +45 for overrun, -15 for shortened).
    pub delta_minutes: i32,
    pub timestamp_utc: DateTime<Utc>,
    /// Pointer to a full payload stored elsewhere (blob store row id, file path, etc.).
    pub payload_ref: String,
}

impl ContextChangeEvent {
    /// Minimal invariants for safe downstream processing.
    pub fn validate(&self) -> Result<(), String> {
        if self.change_type.trim().is_empty() {
            return Err("change_type must be non-empty".to_string());
        }
        if self.payload_ref.trim().is_empty() {
            return Err("payload_ref must be non-empty".to_string());
        }
        Ok(())
    }
}

/// Severity classification for a disruption.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum DisruptionSeverity {
    Minor,
    Major,
    Critical,
}

/// A classified disruption emitted by a disruption detector.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DisruptionEvent {
    pub severity: DisruptionSeverity,
    pub cascade_count: u32,
    pub reason: String,
    /// Reference to the originating `ContextChangeEvent` (id in an event store).
    pub context_event_id: String,
    pub timestamp_utc: DateTime<Utc>,
}

impl DisruptionEvent {
    pub fn validate(&self) -> Result<(), String> {
        if self.reason.trim().is_empty() {
            return Err("reason must be non-empty".to_string());
        }
        if self.context_event_id.trim().is_empty() {
            return Err("context_event_id must be non-empty".to_string());
        }
        Ok(())
    }
}

/// Snapshot of a replanned schedule.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct UpdatedSchedule {
    /// Local day the schedule applies to.
    pub day: NaiveDate,
    /// Ordered task identifiers for the day.
    pub task_order: Vec<String>,
    pub swapped_out: Vec<String>,
    pub swapped_in: Vec<String>,
    /// Energy level used while producing this schedule (0..N; semantics owned by kernel).
    pub energy_level: i32,
}

impl UpdatedSchedule {
    pub fn validate(&self) -> Result<(), String> {
        if self.task_order.iter().any(|t| t.trim().is_empty()) {
            return Err("task_order must not contain empty task ids".to_string());
        }
        Ok(())
    }
}

/// A queued automatable action to be drafted/executed by a worker.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DelegationItem {
    pub task_id: String,
    /// Target channel (e.g. "slack", "email", "imessage").
    pub channel: String,
    /// Draft type (e.g. "reply", "schedule", "follow_up").
    pub draft_type: String,
    /// Higher means more urgent.
    pub priority: u8,
}

impl DelegationItem {
    pub fn validate(&self) -> Result<(), String> {
        if self.task_id.trim().is_empty() {
            return Err("task_id must be non-empty".to_string());
        }
        if self.channel.trim().is_empty() {
            return Err("channel must be non-empty".to_string());
        }
        if self.draft_type.trim().is_empty() {
            return Err("draft_type must be non-empty".to_string());
        }
        Ok(())
    }
}

/// Queue of delegated work for automation.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct DelegationQueue {
    pub items: Vec<DelegationItem>,
}

impl DelegationQueue {
    pub fn validate(&self) -> Result<(), String> {
        for (idx, item) in self.items.iter().enumerate() {
            item.validate()
                .map_err(|e| format!("items[{idx}]: {e}"))?;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    #[test]
    fn context_change_event_json_roundtrip_is_stable() {
        let ev = ContextChangeEvent {
            source: ContextSource::Calendar,
            change_type: "meeting_extended".to_string(),
            delta_minutes: 45,
            timestamp_utc: Utc.with_ymd_and_hms(2026, 2, 21, 8, 25, 0).unwrap(),
            payload_ref: "gcal:event:abc123".to_string(),
        };
        ev.validate().unwrap();

        let json = serde_json::to_string(&ev).unwrap();
        // Ensure key names and enum casing match the spec.
        assert!(json.contains("\"source\":\"calendar\""));
        assert!(json.contains("\"change_type\":"));
        assert!(json.contains("\"delta_minutes\":45"));
        assert!(json.contains("\"timestamp_utc\":"));
        assert!(json.contains("\"payload_ref\":"));

        let back: ContextChangeEvent = serde_json::from_str(&json).unwrap();
        assert_eq!(back, ev);
    }

    #[test]
    fn disruption_event_json_roundtrip_is_stable() {
        let ev = DisruptionEvent {
            severity: DisruptionSeverity::Major,
            cascade_count: 3,
            reason: "calendar overrun".to_string(),
            context_event_id: "evt_001".to_string(),
            timestamp_utc: Utc.with_ymd_and_hms(2026, 2, 21, 8, 26, 0).unwrap(),
        };
        ev.validate().unwrap();

        let json = serde_json::to_string(&ev).unwrap();
        assert!(json.contains("\"severity\":\"major\""));
        assert!(json.contains("\"cascade_count\":3"));

        let back: DisruptionEvent = serde_json::from_str(&json).unwrap();
        assert_eq!(back, ev);
    }

    #[test]
    fn updated_schedule_json_roundtrip_is_stable() {
        let sched = UpdatedSchedule {
            day: NaiveDate::from_ymd_opt(2026, 2, 21).unwrap(),
            task_order: vec!["task_a".into(), "task_b".into()],
            swapped_out: vec!["task_gym".into()],
            swapped_in: vec!["task_pset".into()],
            energy_level: 2,
        };
        sched.validate().unwrap();

        let json = serde_json::to_string(&sched).unwrap();
        assert!(json.contains("\"day\":"));
        assert!(json.contains("\"task_order\":["));

        let back: UpdatedSchedule = serde_json::from_str(&json).unwrap();
        assert_eq!(back, sched);
    }

    #[test]
    fn delegation_queue_json_roundtrip_is_stable_and_validates() {
        let q = DelegationQueue {
            items: vec![DelegationItem {
                task_id: "task_123".into(),
                channel: "slack".into(),
                draft_type: "reply".into(),
                priority: 10,
            }],
        };
        q.validate().unwrap();

        let json = serde_json::to_string(&q).unwrap();
        assert!(json.contains("\"items\":["));
        assert!(json.contains("\"task_id\":"));

        let back: DelegationQueue = serde_json::from_str(&json).unwrap();
        assert_eq!(back, q);
    }

    #[test]
    fn basic_validation_invariants_fail_when_fields_empty() {
        let bad = ContextChangeEvent {
            source: ContextSource::Slack,
            change_type: " ".to_string(),
            delta_minutes: 0,
            timestamp_utc: Utc.with_ymd_and_hms(2026, 2, 21, 8, 25, 0).unwrap(),
            payload_ref: "".to_string(),
        };
        assert!(bad.validate().is_err());

        let bad2 = DisruptionEvent {
            severity: DisruptionSeverity::Minor,
            cascade_count: 0,
            reason: "".to_string(),
            context_event_id: " ".to_string(),
            timestamp_utc: Utc.with_ymd_and_hms(2026, 2, 21, 8, 26, 0).unwrap(),
        };
        assert!(bad2.validate().is_err());

        let bad3 = DelegationQueue {
            items: vec![DelegationItem {
                task_id: "".to_string(),
                channel: "slack".to_string(),
                draft_type: "reply".to_string(),
                priority: 1,
            }],
        };
        assert!(bad3.validate().is_err());
    }
}
