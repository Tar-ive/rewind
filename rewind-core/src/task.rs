//! Task model for the Rust-native scheduling engine (LTS/MTS/STS).
//!
//! This is inspired by the Python engine at `backend/src/engine/*` on the main branch.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TaskStatus {
    Backlog,
    Active,
    InProgress,
    Completed,
    SwappedOut,
    Delegated,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Priority {
    /// Urgent: due within 2 hours
    P0Urgent = 0,
    /// Important: due within 24 hours
    P1Important = 1,
    /// Normal
    P2Normal = 2,
    /// Background
    P3Background = 3,
}

/// Core task type.
///
/// Note: we keep this small + serializable. Storage (files, sqlite, redis) is a later layer.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Task {
    pub id: String,
    pub title: String,

    pub status: TaskStatus,
    pub priority: Priority,

    /// Minutes.
    pub estimated_duration: i32,

    /// 1-5 energy cost.
    pub energy_cost: i32,

    /// 1-5 cognitive load.
    pub cognitive_load: i32,

    /// Optional hard deadline (UTC).
    pub deadline: Option<DateTime<Utc>>,

    /// 0-10, higher means more urgent.
    pub deadline_urgency: i32,
}

impl Task {
    pub fn new(id: impl Into<String>, title: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            title: title.into(),
            status: TaskStatus::Backlog,
            priority: Priority::P2Normal,
            estimated_duration: 30,
            energy_cost: 3,
            cognitive_load: 3,
            deadline: None,
            deadline_urgency: 0,
        }
    }

    pub fn with_deadline(mut self, deadline: DateTime<Utc>) -> Self {
        self.deadline = Some(deadline);
        self
    }

    pub fn with_duration(mut self, minutes: i32) -> Self {
        self.estimated_duration = minutes;
        self
    }

    pub fn with_energy(mut self, energy_cost: i32) -> Self {
        self.energy_cost = energy_cost;
        self
    }

    pub fn with_cognitive(mut self, cognitive_load: i32) -> Self {
        self.cognitive_load = cognitive_load;
        self
    }

    pub fn with_deadline_urgency(mut self, urgency: i32) -> Self {
        self.deadline_urgency = urgency;
        self
    }
}
