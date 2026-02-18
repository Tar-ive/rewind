//! Signal types for profiler integration

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// An explicit signal from user input or data sources
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ExplicitSignal {
    /// Source of the signal (e.g., "composio", "gcal", "manual")
    pub source: String,
    /// Category of the signal
    pub category: String,
    /// Text content
    pub text: String,
    /// Metadata as key-value pairs
    pub metadata: HashMap<String, String>,
}

impl ExplicitSignal {
    /// Create a new explicit signal
    pub fn new(
        source: impl Into<String>,
        category: impl Into<String>,
        text: impl Into<String>,
    ) -> Self {
        Self {
            source: source.into(),
            category: category.into(),
            text: text.into(),
            metadata: HashMap::new(),
        }
    }

    /// Add metadata
    pub fn with_metadata(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.metadata.insert(key.into(), value.into());
        self
    }
}

/// An implicit signal inferred from behavior/patterns
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ImplicitSignal {
    /// Source of inference
    pub source: String,
    /// Type of pattern detected
    pub pattern_type: PatternType,
    /// Human-readable description
    pub description: String,
    /// Metadata
    pub metadata: HashMap<String, String>,
}

impl ImplicitSignal {
    /// Create a new implicit signal
    pub fn new(
        source: impl Into<String>,
        pattern_type: PatternType,
        description: impl Into<String>,
    ) -> Self {
        Self {
            source: source.into(),
            pattern_type,
            description: description.into(),
            metadata: HashMap::new(),
        }
    }
}

/// Pattern types for implicit signals (same as Python version)
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum PatternType {
    #[serde(rename = "working_style")]
    WorkingStyle,
    #[serde(rename = "peak_hours")]
    PeakHours,
    #[serde(rename = "energy_curve")]
    EnergyCurve,
    #[serde(rename = "goal_adherence")]
    GoalAdherence,
    #[serde(rename = "finance_discipline")]
    FinanceDiscipline,
    #[serde(rename = "engagement")]
    Engagement,
    #[serde(rename = "generic")]
    Generic,
}

impl PatternType {
    /// Weight boost for readiness scoring
    pub fn readiness_boost(&self) -> f64 {
        match self {
            PatternType::WorkingStyle | PatternType::PeakHours => 0.05,
            PatternType::EnergyCurve => 0.03,
            PatternType::GoalAdherence => 0.08,
            PatternType::FinanceDiscipline => 0.06,
            PatternType::Engagement => 0.04,
            PatternType::Generic => 0.01,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_explicit_signal() {
        let signal = ExplicitSignal::new("composio", "goal", "Stanford grad school is a stretch target")
            .with_metadata("confidence", "0.85");
        
        assert_eq!(signal.source, "composio");
        assert_eq!(signal.metadata.get("confidence"), Some(&"0.85".to_string()));
    }

    #[test]
    fn test_implicit_signal_boosts() {
        assert_eq!(PatternType::WorkingStyle.readiness_boost(), 0.05);
        assert_eq!(PatternType::GoalAdherence.readiness_boost(), 0.08);
    }
}
