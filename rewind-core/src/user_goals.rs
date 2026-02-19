//! User goal capture + parsing.
//!
//! Rewind's "learning" should be file-backed (similar to OpenClaw memory):
//! goals and preferences live in simple markdown/JSON, with deterministic extraction.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Horizon {
    Long,
    Medium,
    Short,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct UserGoal {
    pub horizon: Horizon,
    pub text: String,
}

/// Parse ~/.rewind/goals.md-style markdown into structured goals.
///
/// Expected headings:
/// - "## Long-term"
/// - "## Medium-term"
/// - "## Short-term"
///
/// Under each, bullet items:
/// - "- <goal text>"
pub fn parse_goals_md(md: &str) -> Vec<UserGoal> {
    let mut horizon: Option<Horizon> = None;
    let mut out = Vec::new();

    for line in md.lines() {
        let l = line.trim();
        if l.starts_with("## ") {
            let heading = l.trim_start_matches("## ").trim().to_lowercase();
            horizon = match heading.as_str() {
                "long-term" | "long term" | "long" => Some(Horizon::Long),
                "medium-term" | "medium term" | "medium" => Some(Horizon::Medium),
                "short-term" | "short term" | "short" => Some(Horizon::Short),
                _ => None,
            };
            continue;
        }

        if let Some(h) = horizon {
            if let Some(rest) = l.strip_prefix("- ") {
                let text = rest.trim().to_string();
                if !text.is_empty() {
                    out.push(UserGoal { horizon: h, text });
                }
            }
        }
    }

    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_goals_md() {
        let md = r#"
# Rewind Goals

## Long-term
- Move to SF

## Medium-term
- Save 15k

## Short-term
- Pay credit card
"#;
        let goals = parse_goals_md(md);
        assert_eq!(goals.len(), 3);
        assert_eq!(goals[0].horizon, Horizon::Long);
        assert_eq!(goals[1].horizon, Horizon::Medium);
        assert_eq!(goals[2].horizon, Horizon::Short);
    }
}
