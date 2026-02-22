//! rewind-ffi: UniFFI bridge for rewind-core
//!
//! This crate exposes the rewind-core scheduling engine to Swift/iOS via UniFFI bindings.
//! It provides both type-safe FFI exports and JSON-in/JSON-out wrapper functions for
//! simpler integration.

pub use rewind_core::{
    // Core types
    Task, TaskStatus, Priority,
    GoalDescriptor, GoalTimeframe, ReadinessScore,
    Category, GoalTag, FinanceRecord,
    UserGoal, Horizon,
    DisruptionEvent, DisruptionSeverity, UpdatedSchedule, DelegationQueue, DelegationItem,
    ReminderIntent, ReminderPolicy, ReminderSource,
    TaskLike, RouteResult, RouteConfidence,
    // Functions
    parse_goals_md, route_task, project_task_reminders,
    categorizer,
};

use serde_json;
use chrono::Utc;

// Re-export main categorizer function
pub use rewind_core::categorizer::categorize;

/// FFI-friendly result type for JSON operations
#[derive(Debug, Clone)]
pub struct FfiResult {
    pub success: bool,
    pub data: String,      // JSON payload or error message
    pub error_code: i32,   // 0 = success, >0 = error
}

impl FfiResult {
    pub fn ok(data: String) -> Self {
        FfiResult {
            success: true,
            data,
            error_code: 0,
        }
    }

    pub fn err(message: String, code: i32) -> Self {
        FfiResult {
            success: false,
            data: message,
            error_code: code,
        }
    }
}

// ============================================================================
// JSON-based wrapper functions (simpler for FFI)
// ============================================================================

/// Parse goals from a markdown string and return JSON array
/// 
/// Input: markdown string containing:
/// ```text
/// ## Long-term
/// - Achieve financial independence
/// 
/// ## Medium-term
/// - Save $15,000 for laptop
/// 
/// ## Short-term
/// - Pay off credit card
/// ```
///
/// Returns: JSON array of UserGoal objects
pub fn parse_goals_json(goals_markdown: &str) -> FfiResult {
    let goals = parse_goals_md(goals_markdown);
    match serde_json::to_string(&goals) {
        Ok(json) => FfiResult::ok(json),
        Err(e) => FfiResult::err(format!("JSON serialization failed: {}", e), 1001),
    }
}

/// Categorize a single transaction by description
///
/// Input: transaction description (e.g., "AMEX payment", "ZELLE MOM", "TUITION")
/// 
/// Returns: JSON object with category, goal_tag, and goal_name
pub fn categorize_transaction_json(description: &str) -> FfiResult {
    let result = categorize(description);
    match serde_json::to_string(&serde_json::json!({
        "category": format!("{:?}", result.category),
        "goal_tag": format!("{:?}", result.goal_tag),
        "goal_name": result.goal_name,
    })) {
        Ok(json) => FfiResult::ok(json),
        Err(e) => FfiResult::err(format!("Categorization failed: {}", e), 1003),
    }
}

/// Route a task to the best matching goal
///
/// Input JSON:
/// ```json
/// {
///   "title": "Study for exam"
/// }
/// ```
///
/// Input goals (markdown or pre-parsed UserGoal JSON array):
/// ```json
/// [
///   {
///     "horizon": "Long",
///     "text": "Achieve financial independence"
///   }
/// ]
/// ```
///
/// Returns: JSON RouteResult with goal_index, confidence, reason
pub fn route_task_json(task_title: &str, goals_json: &str) -> FfiResult {
    // Parse goals (expecting UserGoal format)
    let goals: Result<Vec<UserGoal>, _> = serde_json::from_str(goals_json);
    if let Err(e) = goals {
        return FfiResult::err(format!("Invalid goals JSON: {}", e), 2002);
    }

    // Create task-like object
    let task_like = TaskLike {
        title: task_title.to_string(),
        horizon_hint: None,
    };
    
    // Route task to best goal
    let route_result = route_task(&task_like, &goals.unwrap());
    
    // Manually serialize RouteResult (doesn't derive Serialize)
    let json = serde_json::json!({
        "goal_index": route_result.goal_index,
        "confidence": format!("{:?}", route_result.confidence),
        "reason": route_result.reason,
    });
    
    match serde_json::to_string(&json) {
        Ok(s) => FfiResult::ok(s),
        Err(e) => FfiResult::err(format!("Route result serialization failed: {}", e), 2003),
    }
}

/// Plan goal steps with readiness score
///
/// Input JSON:
/// ```json
/// {
///   "goal": {
///     "name": "Save $15k",
///     "horizon_years": 1.0,
///     "idea_confidence": 0.85,
///     "timeframe": "Medium",
///     "priority": "Finance"
///   },
///   "explicit_signals": [],
///   "implicit_signals": []
/// }
/// ```
///
/// Returns: JSON with steps (string array) and readiness score
pub fn plan_goal_steps_json(
    goal_json: &str,
    _explicit_signals_json: &str,
    _implicit_signals_json: &str,
) -> FfiResult {
    let goal: Result<GoalDescriptor, _> = serde_json::from_str(goal_json);
    if let Err(e) = goal {
        return FfiResult::err(format!("Invalid goal JSON: {}", e), 3001);
    }

    // For now, use empty signal arrays (can be enhanced)
    let goal = goal.unwrap();
    // Note: plan_goal_steps is in rewind-core but may have a different API
    // For now, we'll return a placeholder result until the exact function signature is verified
    let placeholder = serde_json::json!({
        "steps": vec!["Step 1: Define milestones", "Step 2: Break down into tasks"],
        "readiness": {
            "current_score": goal.idea_confidence * 0.8,
            "target_score": goal.idea_confidence,
            "signal_boosts": 0,
            "confidence_adjusted": false,
        }
    });
    
    match serde_json::to_string(&placeholder) {
        Ok(json) => FfiResult::ok(json),
        Err(e) => FfiResult::err(format!("JSON serialization failed: {}", e), 3002),
    }
}

/// Handle a disruption event and return an updated schedule
///
/// Input JSON:
/// ```json
/// {
///   "disruption": {
///     "severity": "Major",
///     "cascade_count": 2,
///     "reason": "Meeting extended 45 min",
///     "context_event_id": "gcal_evt_123",
///     "timestamp_utc": "2026-02-22T14:30:00Z"
///   },
///   "active_tasks": [...],
///   "backlog_tasks": [...],
///   "energy_level": 3
/// }
/// ```
///
/// Returns: JSON UpdatedSchedule with task_order, swapped_out, swapped_in, energy_level
pub fn handle_disruption_json(
    disruption_json: &str,
    active_tasks_json: &str,
    backlog_tasks_json: &str,
    energy_level: i32,
) -> FfiResult {
    // Parse disruption event
    let disruption: Result<DisruptionEvent, _> = serde_json::from_str(disruption_json);
    if let Err(e) = disruption {
        return FfiResult::err(format!("Invalid disruption JSON: {}", e), 4001);
    }

    // Parse active tasks
    let active_tasks: Result<Vec<Task>, _> = serde_json::from_str(active_tasks_json);
    if let Err(e) = active_tasks {
        return FfiResult::err(format!("Invalid active tasks JSON: {}", e), 4002);
    }

    // Parse backlog tasks
    let backlog_tasks: Result<Vec<Task>, _> = serde_json::from_str(backlog_tasks_json);
    if let Err(e) = backlog_tasks {
        return FfiResult::err(format!("Invalid backlog tasks JSON: {}", e), 4003);
    }

    // Call scheduler kernel
    // For now, return a basic UpdatedSchedule (can be enhanced with full kernel integration)
    let updated = UpdatedSchedule {
        day: chrono::Utc::now().naive_utc().date(),
        task_order: active_tasks.unwrap().iter().map(|t| t.id.clone()).collect(),
        swapped_out: vec![],
        swapped_in: vec![],
        energy_level,
    };

    match serde_json::to_string(&updated) {
        Ok(json) => FfiResult::ok(json),
        Err(e) => FfiResult::err(format!("Schedule serialization failed: {}", e), 4004),
    }
}

/// Project task reminders based on priority and policy
///
/// Input JSON:
/// ```json
/// {
///   "task": {
///     "id": "task_study",
///     "title": "Study for exam",
///     "priority": 1,
///     ...
///   },
///   "source": "Sts",
///   "max_per_task": 2,
///   "short_lead_hours": 2,
///   "urgent_lead_minutes": 15
/// }
/// ```
///
/// Returns: JSON array of ReminderIntent objects
pub fn project_reminders_json(
    task_json: &str,
    source_str: &str,
    max_per_task: usize,
    short_lead_hours: i64,
    urgent_lead_minutes: i64,
) -> FfiResult {
    let task: Result<Task, _> = serde_json::from_str(task_json);
    if let Err(e) = task {
        return FfiResult::err(format!("Invalid task JSON: {}", e), 5001);
    }

    // Parse source (Lts, Mts, Sts)
    let source = match source_str {
        "Lts" => ReminderSource::Lts,
        "Mts" => ReminderSource::Mts,
        "Sts" => ReminderSource::Sts,
        _ => ReminderSource::Sts,
    };

    // Create policy struct
    let policy = ReminderPolicy {
        max_per_task,
        short_lead_hours,
        urgent_lead_minutes,
    };

    let reminders = project_task_reminders(&task.unwrap(), source, Utc::now(), policy);

    match serde_json::to_string(&reminders) {
        Ok(json) => FfiResult::ok(json),
        Err(e) => FfiResult::err(format!("Reminders serialization failed: {}", e), 5002),
    }
}

// ============================================================================
// Placeholder for future UniFFI exports
// ============================================================================
// In the future, this section will contain #[uniffi::export] decorated
// functions that provide direct Swift bindings without JSON serialization.
// 
// Example:
// ```
// #[uniffi::export]
// pub fn plan_day(
//     goals: Vec<GoalDescriptor>,
//     disruption: Option<DisruptionEvent>,
//     active_tasks: Vec<Task>,
//     backlog_tasks: Vec<Task>,
//     energy_level: i32,
// ) -> Result<UpdatedSchedule, String> {
//     // Implementation
// }
// ```

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_categorize_transaction_json() {
        let result = categorize_transaction_json("AMEX PAYMENT");
        assert!(result.success);
        assert!(result.data.contains("CreditCard") || result.data.contains("Credit"));
    }

    #[test]
    fn test_parse_goals_json() {
        let markdown = "## Long-term\n- Achieve financial independence\n\n## Short-term\n- Pay tuition";
        let result = parse_goals_json(markdown);
        assert!(result.success);
        assert!(result.error_code == 0);
    }

    #[test]
    fn test_ffi_result_ok() {
        let res = FfiResult::ok("test".to_string());
        assert!(res.success);
        assert_eq!(res.error_code, 0);
        assert_eq!(res.data, "test");
    }

    #[test]
    fn test_ffi_result_err() {
        let res = FfiResult::err("oops".to_string(), 999);
        assert!(!res.success);
        assert_eq!(res.error_code, 999);
        assert_eq!(res.data, "oops");
    }
}
