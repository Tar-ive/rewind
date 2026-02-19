//! Deterministic routing: map implicit signals/tasks to explicit user goals.
//!
//! This is intentionally non-LLM-first. We do:
//! 1) cheap heuristics and keyword overlap
//! 2) only then (optional) LLM intent classification for ambiguous cases

use crate::user_goals::{Horizon, UserGoal};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RouteConfidence {
    High,
    Medium,
    Low,
    None,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RouteResult {
    pub goal_index: Option<usize>,
    pub confidence: RouteConfidence,
    pub reason: String,
}

/// Minimal task shape for routing.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TaskLike {
    pub title: String,
    pub horizon_hint: Option<Horizon>,
}

fn tokenize(s: &str) -> Vec<String> {
    let raw: Vec<String> = s
        .to_lowercase()
        .split(|c: char| !c.is_alphanumeric())
        .filter(|t| !t.is_empty())
        .map(|t| t.to_string())
        .collect();

    // Simple synonym expansion (deterministic, no LLM)
    let mut out: Vec<String> = Vec::new();
    for t in raw {
        match t.as_str() {
            // Finance abbreviations
            "cc" => {
                out.push("credit".to_string());
                out.push("card".to_string());
            }
            "autopay" | "payment" | "pay" | "paid" => out.push("pay".to_string()),
            _ => {
                if t.len() >= 3 {
                    out.push(t);
                }
            }
        }
    }

    out
}

/// Route a task to the best matching goal by keyword overlap.
///
/// Scoring:
/// - +2 per overlapping token
/// - +2 bonus if horizon hints match
pub fn route_task(task: &TaskLike, goals: &[UserGoal]) -> RouteResult {
    let task_tokens = tokenize(&task.title);
    if task_tokens.is_empty() || goals.is_empty() {
        return RouteResult {
            goal_index: None,
            confidence: RouteConfidence::None,
            reason: "no tokens or no goals".to_string(),
        };
    }

    let mut best: Option<(usize, i32, usize)> = None; // (idx, score, overlaps)

    for (i, g) in goals.iter().enumerate() {
        let goal_tokens = tokenize(&g.text);
        let mut overlaps = 0usize;
        for t in &task_tokens {
            if goal_tokens.iter().any(|gt| gt == t) {
                overlaps += 1;
            }
        }
        let mut score = (overlaps as i32) * 2;
        if let Some(h) = task.horizon_hint {
            if h == g.horizon {
                score += 2;
            }
        }

        match best {
            None => best = Some((i, score, overlaps)),
            Some((_, best_score, _)) if score > best_score => best = Some((i, score, overlaps)),
            _ => {}
        }
    }

    let Some((idx, score, overlaps)) = best else {
        return RouteResult {
            goal_index: None,
            confidence: RouteConfidence::None,
            reason: "no goal candidates".to_string(),
        };
    };

    let (confidence, reason) = if overlaps >= 2 {
        (RouteConfidence::High, format!("{} overlaps (score {})", overlaps, score))
    } else if overlaps == 1 {
        (RouteConfidence::Medium, format!("1 overlap (score {})", score))
    } else if score > 0 {
        (RouteConfidence::Low, format!("horizon bonus only (score {})", score))
    } else {
        (RouteConfidence::None, "no overlap".to_string())
    };

    if confidence == RouteConfidence::None {
        RouteResult { goal_index: None, confidence, reason }
    } else {
        RouteResult { goal_index: Some(idx), confidence, reason }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::user_goals::{parse_goals_md, Horizon};

    /// Regression test: obvious keyword match routes correctly.
    #[test]
    fn test_route_task_keyword_overlap() {
        let goals = parse_goals_md(
            r#"## Long-term
- Move to SF internship

## Medium-term
- Save 15k emergency fund

## Short-term
- Pay credit card
"#,
        );

        let task = TaskLike {
            title: "CC payment | AMEX autopay statement".to_string(),
            horizon_hint: Some(Horizon::Short),
        };

        let r = route_task(&task, &goals);
        assert_eq!(r.goal_index, Some(2));
        assert!(matches!(r.confidence, RouteConfidence::High | RouteConfidence::Medium));
    }

    /// Regression test: horizon hint can break ties / give low confidence.
    #[test]
    fn test_route_task_horizon_bonus_only() {
        let goals = parse_goals_md(
            r#"## Long-term
- Move to SF

## Medium-term
- Save 15k

## Short-term
- Pay tuition
"#,
        );

        let task = TaskLike {
            title: "Daily expenses".to_string(),
            horizon_hint: Some(Horizon::Medium),
        };

        let r = route_task(&task, &goals);
        // No token overlap; horizon bonus only => Low or None.
        assert!(matches!(r.confidence, RouteConfidence::Low | RouteConfidence::None));
    }

    /// Regression test: no goals -> None.
    #[test]
    fn test_route_task_no_goals() {
        let task = TaskLike {
            title: "anything".to_string(),
            horizon_hint: None,
        };
        let r = route_task(&task, &[]);
        assert_eq!(r.goal_index, None);
        assert_eq!(r.confidence, RouteConfidence::None);
    }
}
