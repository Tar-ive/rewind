use serde::{Deserialize, Serialize};

/// Rewind onboarding sufficiency check (Pareto-optimal questioning).
///
/// This mirrors the medical-consultation pattern:
/// ask the single most important next question until we can proceed.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct OnboardDecision {
    pub proceed_to_planning: bool,
    pub assistant_message: String,
}

#[derive(Debug, Clone, Default)]
pub struct OnboardState {
    pub timezone: Option<String>,
    pub has_goals: bool,
    pub has_statement: bool,
}

pub fn decide_next_question(state: &OnboardState) -> OnboardDecision {
    // 1) Timezone is required for deadlines + calendar
    if state.timezone.as_deref().unwrap_or("").trim().is_empty() {
        return OnboardDecision {
            proceed_to_planning: false,
            assistant_message: "What timezone are you in? (IANA format like America/Chicago)".to_string(),
        };
    }

    // 2) Goals required
    if !state.has_goals {
        return OnboardDecision {
            proceed_to_planning: false,
            assistant_message: "What are your long-, medium-, and short-term goals? (1-3 bullets each is enough to start)".to_string(),
        };
    }

    // 3) Statement required to generate implicit finance signals
    if !state.has_statement {
        return OnboardDecision {
            proceed_to_planning: false,
            assistant_message: "Do you want to import a statement now (AMEX CSV / Chase PDF / Capital One PDF)? If yes, which one?".to_string(),
        };
    }

    OnboardDecision {
        proceed_to_planning: true,
        assistant_message: "Thanks — I have enough information to generate your first plan and time-block your schedule.".to_string(),
    }
}
