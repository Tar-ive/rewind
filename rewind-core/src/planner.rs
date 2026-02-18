//! Goal planner: converts goals + signals into milestone steps with readiness scores.
//! Port of Python `backend/src/goal_logic.py`

use crate::goals::{GoalDescriptor, GoalTimeframe, ReadinessScore};
use crate::signals::{ExplicitSignal, ImplicitSignal, PatternType};

/// Plan goal steps and compute readiness based on signals.
/// Returns (steps, readiness_score).
pub fn plan_goal_steps(
    goal: &GoalDescriptor,
    explicit: &[ExplicitSignal],
    implicit: &[ImplicitSignal],
) -> (Vec<String>, ReadinessScore) {
    let mut steps = Vec::new();
    let base_steps = goal.milestone_count();

    match goal.timeframe {
        GoalTimeframe::Long => {
            steps.push("Research the landscape (institutions, visa, funding).".into());
            steps.push("Build a living-in-SF hypothesis board: housing, cashflow, network.".into());
            if goal.idea_confidence < 0.3 {
                steps.push(
                    "Experiment with exploratory visits or mentorship to validate the target."
                        .into(),
                );
            }
        }
        GoalTimeframe::Medium => {
            steps.push("Break down the $15k target into weekly savings milestones.".into());
            steps.push("Automate tracking using the Composio Google Sheet watcher.".into());
            steps.push(
                "Flag a monthly review to celebrate progress and adjust categories.".into(),
            );
        }
        GoalTimeframe::Short => {
            steps.push(
                "List the exact amounts due for tuition/credit card and payment deadlines.".into(),
            );
            steps.push("Schedule tasks in STS to pay the bills at least one week early.".into());
        }
    }

    // Fill remaining milestones
    while steps.len() < base_steps {
        steps.push(
            "Deepen the signal set: journal reflections and log progress in Flatnotes.".into(),
        );
    }

    // Compute readiness
    let signal_ratio = signal_support_ratio(goal, explicit);
    let mut readiness = (goal.idea_confidence + signal_ratio).min(1.0);

    // Energy bumps from implicit signals
    let energy_bumps: f64 = implicit
        .iter()
        .map(|s| match s.pattern_type {
            PatternType::WorkingStyle | PatternType::PeakHours => 0.05,
            PatternType::GoalAdherence => 0.08,
            PatternType::FinanceDiscipline => 0.06,
            _ => 0.0,
        })
        .sum();

    readiness = (readiness + energy_bumps).min(1.0);

    (steps, ReadinessScore::new(readiness))
}

/// Calculate how many explicit signals match this goal
fn signal_support_ratio(goal: &GoalDescriptor, explicit: &[ExplicitSignal]) -> f64 {
    let goal_lower = goal.name.to_lowercase();
    let matches = explicit
        .iter()
        .filter(|s| s.text.to_lowercase().contains(&goal_lower))
        .count();
    (matches as f64 * 0.25).min(1.0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::signals::PatternType;

    fn make_explicit(texts: &[&str]) -> Vec<ExplicitSignal> {
        texts
            .iter()
            .map(|t| ExplicitSignal::new("test", "goal", *t))
            .collect()
    }

    fn make_implicit(types: &[PatternType]) -> Vec<ImplicitSignal> {
        types
            .iter()
            .map(|t| ImplicitSignal::new("test", *t, "test signal"))
            .collect()
    }

    #[test]
    fn test_move_to_sf_long_term() {
        let goal = GoalDescriptor::new("Move to SF", 2.0, 0.1, GoalTimeframe::Long, "career");
        let (steps, readiness) = plan_goal_steps(&goal, &[], &[]);
        assert!(steps.len() >= 4);
        assert!(steps[0].to_lowercase().contains("research"));
        assert!(readiness.value() <= 0.2);
    }

    #[test]
    fn test_support_parents_short_term() {
        let goal = GoalDescriptor::new(
            "Support parents monthly",
            0.2,
            0.7,
            GoalTimeframe::Short,
            "family",
        );
        let (steps, readiness) = plan_goal_steps(&goal, &[], &[]);
        assert!(steps.len() >= 2);
        assert!((readiness.value() - 0.7).abs() < 0.05);
    }

    #[test]
    fn test_save_15k_medium_term() {
        let goal = GoalDescriptor::new(
            "Save 15k by semester",
            0.5,
            0.5,
            GoalTimeframe::Medium,
            "finance",
        );
        let (steps, _) = plan_goal_steps(&goal, &[], &[]);
        assert!(steps.iter().any(|s| s.to_lowercase().contains("weekly")));
        assert!(steps
            .iter()
            .any(|s| s.to_lowercase().contains("automate tracking")));
    }

    #[test]
    fn test_pay_credit_card_short_term() {
        let goal = GoalDescriptor::new(
            "Pay credit card off",
            0.1,
            0.8,
            GoalTimeframe::Short,
            "finance",
        );
        let (steps, _) = plan_goal_steps(&goal, &[], &[]);
        assert!(steps[0].to_lowercase().starts_with("list the exact amounts"));
    }

    #[test]
    fn test_signals_boost_readiness() {
        let goal = GoalDescriptor::new(
            "Support parents monthly",
            0.2,
            0.3,
            GoalTimeframe::Short,
            "family",
        );
        let explicit = make_explicit(&["Support parents monthly via cash transfers"]);
        let implicit = make_implicit(&[PatternType::WorkingStyle, PatternType::PeakHours]);
        let (_, readiness) = plan_goal_steps(&goal, &explicit, &implicit);
        assert!(readiness.value() > 0.5);
    }

    #[test]
    fn test_stanford_low_confidence_with_signals() {
        let goal = GoalDescriptor::new(
            "Go to Stanford grad school",
            5.0,
            0.0,
            GoalTimeframe::Long,
            "education",
        );
        let explicit =
            make_explicit(&["Goal: Go to Stanford grad school is a stretch target"]);
        let implicit = make_implicit(&[PatternType::GoalAdherence]);
        let (steps, readiness) = plan_goal_steps(&goal, &explicit, &implicit);
        assert!(steps.len() >= 4);
        assert!(readiness.value() > 0.0);
    }

    #[test]
    fn test_readiness_tracks_confidence() {
        let goal_high =
            GoalDescriptor::new("Support parents", 0.2, 0.7, GoalTimeframe::Short, "family");
        let goal_low =
            GoalDescriptor::new("Move to SF", 2.0, 0.1, GoalTimeframe::Long, "career");

        let (_, r_high) = plan_goal_steps(&goal_high, &[], &[]);
        let (_, r_low) = plan_goal_steps(&goal_low, &[], &[]);

        assert!(r_high.value() > r_low.value());
    }
}
