//! Goal descriptor types for LTS/MTS/STS scheduling

use serde::{Deserialize, Serialize};

/// Timeframe classification for goals
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum GoalTimeframe {
    #[serde(rename = "long")]
    Long,    // Multi-year goals
    #[serde(rename = "medium")]
    Medium,  // Months to a year
    #[serde(rename = "short")]
    Short,   // Days to weeks
}

impl GoalTimeframe {
    /// Calculate default milestone count based on timeframe and horizon
    pub fn milestone_count(&self, horizon_years: f64) -> usize {
        match self {
            GoalTimeframe::Short => (horizon_years * 4.0).max(2.0) as usize,
            GoalTimeframe::Medium => (horizon_years * 2.0).max(3.0) as usize,
            GoalTimeframe::Long => (horizon_years * 1.5 + 1.0).max(4.0) as usize,
        }
    }
}

/// A goal descriptor with readiness scoring
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GoalDescriptor {
    /// Name of the goal
    pub name: String,
    /// Horizon in years
    pub horizon_years: f64,
    /// Confidence level (0.0 - 1.0)
    pub idea_confidence: f64,
    /// Timeframe classification
    pub timeframe: GoalTimeframe,
    /// Priority category
    pub priority: String,
}

impl GoalDescriptor {
    /// Create a new goal descriptor
    pub fn new(
        name: impl Into<String>,
        horizon_years: f64,
        idea_confidence: f64,
        timeframe: GoalTimeframe,
        priority: impl Into<String>,
    ) -> Self {
        Self {
            name: name.into(),
            horizon_years,
            idea_confidence: idea_confidence.clamp(0.0, 1.0),
            timeframe,
            priority: priority.into(),
        }
    }

    /// Calculate milestone count for this goal
    pub fn milestone_count(&self) -> usize {
        self.timeframe.milestone_count(self.horizon_years)
    }
}

/// Readiness score for a goal (0.0 - 1.0)
#[derive(Debug, Clone, Copy, PartialEq, PartialOrd)]
pub struct ReadinessScore(pub f64);

impl ReadinessScore {
    /// Create a new readiness score, clamped to 0.0-1.0
    pub fn new(score: f64) -> Self {
        Self(score.clamp(0.0, 1.0))
    }

    /// Check if this indicates readiness (> 0.5)
    pub fn is_ready(&self) -> bool {
        self.0 > 0.5
    }

    /// Get the raw value
    pub fn value(&self) -> f64 {
        self.0
    }
}

impl Default for ReadinessScore {
    fn default() -> Self {
        Self(0.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_goal_descriptor_milestones() {
        // Short-term goal (1 month)
        let short = GoalDescriptor::new("Pay credit card", 0.1, 0.8, GoalTimeframe::Short, "finance");
        assert_eq!(short.milestone_count(), 2);

        // Medium-term goal (6 months)
        let medium = GoalDescriptor::new("Save 15k", 0.5, 0.5, GoalTimeframe::Medium, "finance");
        assert_eq!(medium.milestone_count(), 3);

        // Long-term goal (2 years)
        let long = GoalDescriptor::new("Move to SF", 2.0, 0.1, GoalTimeframe::Long, "career");
        assert_eq!(long.milestone_count(), 4); // 2.0 * 1.5 + 1 = 4
    }

    #[test]
    fn test_readiness_score() {
        let score = ReadinessScore::new(0.7);
        assert!(score.is_ready());
        assert_eq!(score.value(), 0.7);

        let not_ready = ReadinessScore::new(0.3);
        assert!(!not_ready.is_ready());
    }

    #[test]
    fn test_confidence_clamping() {
        let high = GoalDescriptor::new("Test", 1.0, 1.5, GoalTimeframe::Short, "test");
        assert_eq!(high.idea_confidence, 1.0);

        let low = GoalDescriptor::new("Test", 1.0, -0.5, GoalTimeframe::Short, "test");
        assert_eq!(low.idea_confidence, 0.0);
    }
}
