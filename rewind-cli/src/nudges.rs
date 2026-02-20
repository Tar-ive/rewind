use anyhow::{bail, Context, Result};
use chrono::{DateTime, Duration, Timelike, Utc, TimeZone};
use chrono_tz::Tz;
use rewind_finance::{parse_amex_csv, TaskEmitter};

use crate::calendar;

/// Build 3 daily "nudge" events (pay/check/review) from finance-derived tasks.
///
/// Goal:
/// - reduce overwhelm: never more than 3 events/day
/// - keep events short and action-oriented
pub fn build_nudges_from_amex(
    csv_path: &std::path::Path,
    tz: Tz,
    now_utc: DateTime<Utc>,
) -> Result<Vec<calendar::CalendarEvent>> {
    if !csv_path.exists() {
        bail!("CSV not found: {} (pass --csv <path>)", csv_path.display());
    }

    let txns = parse_amex_csv(csv_path)
        .with_context(|| format!("parsing {}", csv_path.display()))?;
    let finance_tasks = TaskEmitter::emit(&txns);

    // Pick up to 1 task per horizon bucket (S/M/L) by urgency.
    let mut best_short: Option<(String, rewind_core::Category, rewind_core::GoalTag, f64)> = None;
    let mut best_med: Option<(String, rewind_core::Category, rewind_core::GoalTag, f64)> = None;
    let mut best_long: Option<(String, rewind_core::Category, rewind_core::GoalTag, f64)> = None;

    for ft in finance_tasks {
        let entry = (ft.goal_name, ft.category, ft.goal_tag, ft.urgency);
        match ft.goal_tag {
            rewind_core::GoalTag::Short => {
                if best_short.as_ref().map(|b| entry.3 > b.3).unwrap_or(true) {
                    best_short = Some(entry);
                }
            }
            rewind_core::GoalTag::Medium => {
                if best_med.as_ref().map(|b| entry.3 > b.3).unwrap_or(true) {
                    best_med = Some(entry);
                }
            }
            rewind_core::GoalTag::Long => {
                if best_long.as_ref().map(|b| entry.3 > b.3).unwrap_or(true) {
                    best_long = Some(entry);
                }
            }
        }
    }

    let mut chosen: Vec<(rewind_core::GoalTag, String, i32)> = Vec::new();

    if let Some((goal_name, _cat, tag, _u)) = best_short {
        chosen.push((tag, format!("Pay: {} (2–5 min)", goal_name), 5));
    }
    chosen.push((rewind_core::GoalTag::Short, "Check: upcoming bills / minimums (5 min)".to_string(), 5));

    if let Some((goal_name, _cat, tag, _u)) = best_med {
        chosen.push((tag, format!("Review: {} (10 min)", goal_name), 10));
    } else {
        chosen.push((rewind_core::GoalTag::Medium, "Review: spending since last check-in (10 min)".to_string(), 10));
    }

    // If we have a long-term anchor, replace the medium review with a long-term nudge (still max 3).
    if let Some((goal_name, _cat, tag, _u)) = best_long {
        // Keep three events; replace 3rd slot.
        chosen[2] = (tag, format!("Plan: {} (10 min)", goal_name), 10);
    }

    // Schedule nudges in 3 separate windows to avoid "stacked" feeling.
    // Defaults: 10:00, 15:00, 19:30 local.
    let local = now_utc.with_timezone(&tz);
    let day = local.date_naive();

    let slots = [
        day.and_hms_opt(10, 0, 0).unwrap(),
        day.and_hms_opt(15, 0, 0).unwrap(),
        day.and_hms_opt(19, 30, 0).unwrap(),
    ];

    let mut start_locals: Vec<DateTime<Tz>> = slots
        .iter()
        .map(|t| tz.from_local_datetime(t).single().unwrap())
        .collect();

    // If a slot is in the past, bump it to next quarter-hour from now.
    for s in start_locals.iter_mut() {
        if local > *s {
            let minute = local.minute();
            let add = match minute % 15 {
                0 => 0,
                r => 15 - r,
            };
            *s = (local + Duration::minutes(add.into()))
                .with_second(0)
                .unwrap()
                .with_nanosecond(0)
                .unwrap();
        }
    }

    let mut events = Vec::new();

    for (idx, (tag, title, minutes)) in chosen.into_iter().take(3).enumerate() {
        let start = *start_locals.get(idx).unwrap_or(&local);
        let end = start + Duration::minutes(minutes.into());
        events.push(calendar::CalendarEvent {
            task_id: format!("nudge-{}-{}", start.format("%Y%m%d"), idx),
            horizon: tag,
            start_utc: start.with_timezone(&Utc),
            end_utc: end.with_timezone(&Utc),
            summary: format!("Rewind Nudge: {}", title),
            description: "Small step. Mark done by adding ' - done' to the title.".to_string(),
        });
    }

    Ok(events)
}
